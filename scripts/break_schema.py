"""Demo lever: rename a field across the whole data collection (and back).

Run:  python -m scripts.break_schema --rename storeLocation store_location
      python -m scripts.break_schema --rename store_location storeLocation     # undo
      python -m scripts.break_schema --rename storeLocation store_location --repair-now   # no watcher needed
"""
import argparse

from downshift import db, repair


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rename", nargs=2, metavar=("OLD", "NEW"), required=True)
    ap.add_argument("--repair-now", action="store_true", help="run repair directly instead of waiting for the watcher")
    args = ap.parse_args()
    old, new = args.rename
    c = db.client()
    data = db.data_coll(c)
    res = data.update_many({old: {"$exists": True}}, {"$rename": {old: new}})
    print(f"renamed {old} -> {new} in {res.modified_count} documents")
    if args.repair_now:
        r = repair.handle_schema_change(db.app_db(c), data)
        print(r)


if __name__ == "__main__":
    main()
