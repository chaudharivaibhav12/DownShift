"""Watch the data collection with a change stream; when documents gain or lose fields, run schema repair.

Run (leave it running in its own terminal):  python -m scripts.watch_schema
Then in another terminal:                    python -m scripts.break_schema --rename storeLocation store_location

Change streams need a replica set (every Atlas cluster, including the free tier).
"""
import threading
import time

from downshift import config, db, repair, schema

QUIET_SECONDS = 3.0  # wait for a bulk update to finish before re-reading the schema


def main():
    c = db.client()
    adb, data = db.app_db(c), db.data_coll(c)
    known = {f["path"] for f in (schema.latest(adb.schema_registry, config.DATA_COLLECTION) or {"fields": []})["fields"]}
    last_event = [0.0]
    pending = threading.Event()

    def worker():
        while True:
            pending.wait()
            while time.time() - last_event[0] < QUIET_SECONDS:
                time.sleep(0.5)
            pending.clear()
            print("[watch] documents changed shape; re-reading schema")
            r = repair.handle_schema_change(adb, data)
            print(f"[watch] schema v{r['version']} changed: {r['changed'] or 'nothing'}")
            for f in r["flagged"]:
                print(f"[watch]   flagged {f}")
            for rep in r["repairs"]:
                status = f"v{rep['from']} -> v{rep.get('to')} gate {rep.get('gate')}" if rep["ok"] else f"FAILED: {rep['error']}"
                print(f"[watch]   repair {rep['skill']}: {status}  (${rep['cost']:.4f}) {rep.get('note', '')}")
            known.clear()
            known.update(f["path"] for f in schema.latest(adb.schema_registry, config.DATA_COLLECTION)["fields"])

    threading.Thread(target=worker, daemon=True).start()
    pipeline = [{"$match": {"operationType": {"$in": ["update", "replace", "insert"]}}}]
    print(f"[watch] watching {config.DATA_DB}.{config.DATA_COLLECTION} for field changes (Ctrl+C to stop)")
    with data.watch(pipeline, full_document=None) as stream:
        for ev in stream:
            desc = ev.get("updateDescription") or {}
            touched = set(desc.get("updatedFields", {})) | set(desc.get("removedFields", []))
            if ev["operationType"] in ("insert", "replace"):
                touched |= set((ev.get("fullDocument") or {}).keys())
            top_level = {t.split(".")[0] for t in touched}
            if desc.get("removedFields") or (top_level - {p.split(".")[0] for p in known}):
                last_event[0] = time.time()
                pending.set()


if __name__ == "__main__":
    main()
