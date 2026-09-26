"""Print stored console answers with their full trace (why a question took the path it took).

Run:  python -m scripts.show_answer "March 2016"     # answers whose question contains this text
      python -m scripts.show_answer                  # the 5 most recent answers
"""
import sys

from bson import json_util

from downshift import db


def main():
    adb = db.app_db()
    q = {"question": {"$regex": sys.argv[1], "$options": "i"}} if len(sys.argv) > 1 else {}
    for a in adb.answers.find(q).sort("ts", -1).limit(5):
        print(f"\n=== {a['question']}\n    {a['ts']:%Y-%m-%d %H:%M:%S} · path {a['path']} · ${a['cost']:.5f} · {a['ms']} ms"
              f" · skill {a.get('skill')} · params {json_util.dumps(a.get('params'))}")
        for t in a.get("trace") or []:
            print("    trace:", t)
        for s in a.get("steps") or []:
            print(f"    step: [{s.get('kind')}] {s.get('name')} · {s.get('detail') or ''}"
                  f"{' · FAILED' if s.get('ok') is False else ''}")
    live = list(adb.skills.find({"status": {"$in": ["promoted", "flagged", "broken"]}},
                                {"skillId": 1, "version": 1, "status": 1, "intent": 1, "createdAt": 1}))
    print("\nlive/flagged/broken skills now:")
    for s in live:
        print(f"  {s['skillId']} v{s['version']} [{s['status']}] created {s.get('createdAt')} - {s.get('intent', '')[:90]}")


if __name__ == "__main__":
    main()
