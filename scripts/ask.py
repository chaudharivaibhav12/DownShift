"""Ask Downshift one question and see which path answered it.

Run:  python -m scripts.ask "Top 3 stores by revenue in March 2016"
"""
import sys

from bson import json_util

from downshift import config, db, schema
from downshift.answer import answer


def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: python -m scripts.ask "your question"')
    question = " ".join(sys.argv[1:])
    c = db.client()
    adb, data = db.app_db(c), db.data_coll(c)
    snap = schema.latest(adb.schema_registry, config.DATA_COLLECTION)
    r = answer(adb, data, question, schema.schema_for_prompt(snap["fields"]))
    for line in r["trace"]:
        print("  " + line)
    print(f"path={r['path']}  cost=${r['cost']:.5f}  skill={r['skill']}")
    print(json_util.dumps(r["rows"], indent=2) if r["rows"] is not None else "no answer")


if __name__ == "__main__":
    main()
