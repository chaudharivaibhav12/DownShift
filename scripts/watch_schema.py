"""Standalone schema watcher (the server already runs one for real databases; use this only without the server,
and don't run both at once). Watches the data collection with a change stream; when documents gain or lose fields,
runs schema repair.

Run:          python -m scripts.watch_schema
Then e.g.:    python -m scripts.break_schema --rename storeLocation store_location

Change streams need a replica set (every Atlas cluster, including the free tier).
"""
from downshift import db, repair
from downshift.watcher import SchemaWatcher


def main():
    c = db.client()
    adb, data = db.app_db(c), db.data_coll(c)

    def on_change(info):
        print(f"[watch] removed {info['removed']} added {info['added']} ({info['count']} events); re-reading schema")
        r = repair.handle_schema_change(adb, data)
        print(f"[watch] schema v{r['version']} changed: {r['changed'] or 'nothing'}")
        for rep in r["repairs"]:
            status = f"v{rep['from']} -> v{rep.get('to')} gate {rep.get('gate')}" if rep["ok"] else f"FAILED: {rep.get('error')}"
            print(f"[watch]   repair {rep['skill']}: {status}  (${rep['cost']:.4f}) {rep.get('note', '')}")

    print("[watch] Ctrl+C to stop")
    SchemaWatcher(adb, data, on_change).run()


if __name__ == "__main__":
    main()
