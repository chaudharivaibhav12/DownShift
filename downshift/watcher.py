"""Live schema watcher: a MongoDB change stream on the data collection that triggers skill repair by itself.

Rename a field in Atlas (Data Explorer, Compass, mongosh, an app deploy...) and Downshift notices, waits for the bulk
update to settle, re-reads the schema and repairs the affected skills - no button, no second terminal.

Change streams need a replica set: every Atlas cluster has one; mongomock (offline demo) does not, so the server
only starts this against a real database.
"""
import threading
import time

from . import config, schema

QUIET_SECONDS = 3.0      # a bulk $rename emits one event per document; wait until they stop
RECONNECT_SECONDS = 5.0


def classify(ev: dict, known_top: set[str]) -> tuple[set[str], set[str]]:
    """(removed, added) top-level field names this change event shows. Both empty = not a shape change."""
    desc = ev.get("updateDescription") or {}
    removed = {f.split(".")[0] for f in desc.get("removedFields", [])}
    touched = {f.split(".")[0] for f in desc.get("updatedFields", {})}
    if ev.get("operationType") in ("insert", "replace"):
        touched |= set((ev.get("fullDocument") or {}).keys())
    added = touched - known_top - {"_id"}
    return removed, added


class SchemaWatcher:
    """on_change(info) is called once per settled burst with {"removed", "added", "count", "renamed"}."""

    def __init__(self, adb, data, on_change, log=print, quiet=QUIET_SECONDS):
        self.adb, self.data, self.on_change, self.log, self.quiet = adb, data, on_change, log, quiet
        self.stop = threading.Event()
        self._lock = threading.Lock()
        self._burst = None          # {"removed", "added", "count", "last"}
        self.status = "starting"

    def known_top(self) -> set[str]:
        snap = schema.latest(self.adb.schema_registry, config.DATA_COLLECTION)
        return {f["path"].split(".")[0].replace("[]", "") for f in (snap or {}).get("fields", [])}

    def feed(self, ev: dict, known_top: set[str]) -> bool:
        """Record one change event; True if it is part of a shape change."""
        removed, added = classify(ev, known_top)
        if not (removed or added):
            return False
        with self._lock:
            b = self._burst or {"removed": set(), "added": set(), "count": 0}
            b["removed"] |= removed
            b["added"] |= added
            b["count"] += 1
            b["last"] = time.time()
            self._burst = b
        return True

    def take_settled(self):
        """The burst, once no new shape events arrived for `quiet` seconds; else None."""
        with self._lock:
            b = self._burst
            if not b or time.time() - b["last"] < self.quiet:
                return None
            self._burst = None
        info = {"removed": sorted(b["removed"]), "added": sorted(b["added"]), "count": b["count"]}
        if len(b["removed"]) == 1 and len(b["added"]) == 1:
            info["renamed"] = [next(iter(b["removed"])), next(iter(b["added"]))]
        return info

    def _settler(self):
        while not self.stop.is_set():
            info = self.take_settled()
            if info:
                try:
                    self.on_change(info)
                except Exception as e:  # noqa: BLE001 - keep watching
                    self.log(f"[watch] repair failed: {type(e).__name__}: {e}")
            time.sleep(0.5)

    def run(self):
        threading.Thread(target=self._settler, daemon=True, name="schema-settler").start()
        pipeline = [{"$match": {"operationType": {"$in": ["update", "replace", "insert"]}}}]
        while not self.stop.is_set():
            try:
                known = self.known_top()
                with self.data.watch(pipeline) as stream:
                    self.status = "watching"
                    self.log(f"[watch] change stream open on {config.DATA_DB}.{config.DATA_COLLECTION}")
                    while not self.stop.is_set():
                        ev = stream.try_next()
                        if ev is None:
                            if self._burst is None:
                                known = self.known_top()   # pick up schema versions written by repairs
                            continue
                        self.feed(ev, known)
            except Exception as e:  # noqa: BLE001 - network blips, stepdowns: reconnect
                self.status = f"reconnecting ({type(e).__name__})"
                self.log(f"[watch] change stream error: {type(e).__name__}: {e}; retrying in {RECONNECT_SECONDS}s")
                self.stop.wait(RECONNECT_SECONDS)

    def start(self):
        threading.Thread(target=self.run, daemon=True, name="schema-watcher").start()
        return self
