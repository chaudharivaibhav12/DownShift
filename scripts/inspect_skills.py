"""Show every skill version: status, params, template and why the gate failed (if it did).

Run:  python -m scripts.inspect_skills                # all skills
      python -m scripts.inspect_skills rejected       # only one status
"""
import sys

from bson import json_util

from downshift import db


def main():
    status = sys.argv[1] if len(sys.argv) > 1 else None
    q = {"status": status} if status else {}
    for s in db.app_db().skills.find(q).sort([("skillId", 1), ("version", 1)]):
        rep = s.get("gateReport") or {}
        print(f"\n=== {s['skillId']} v{s['version']}  [{s['status']}]  gate {rep.get('passed', '?')}/{rep.get('total', '?')}")
        print("intent:", s.get("intent"))
        for k, v in s.get("params", {}).items():
            print(f"  param {k}: {v.get('type')}{' (optional)' if v.get('optional') else ''} - {v.get('description', '')}")
        print("template:", s.get("templateJson", "")[:700])
        for f in rep.get("failures", []):
            print(f"  FAIL: {f.get('question')}\n        error: {f.get('error')}\n        model said: {f.get('modelOutput', '')[:250]!r}")
        print(f"  tests: {len(s.get('gateTests') or [])} gate + {len(s.get('holdoutTests') or [])} held out"
              f"{' · reflected from v' + str(s['reflectedFrom']) + ' (re-gate on ' + rep.get('regateOn', '?') + ')' if s.get('reflectedFrom') else ''}")
        for d in s.get("testDrops") or []:
            print(f"  dropped ({d.get('reason')}): {d.get('question', '')[:90]}  {d.get('detail', '')[:120]}")
        for t in (s.get("gateTests") or [])[:2]:
            print(f"  test example: {t['question']}  params={json_util.dumps(t.get('params'))}")


if __name__ == "__main__":
    main()
