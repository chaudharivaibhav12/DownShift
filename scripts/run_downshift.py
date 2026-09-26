"""Checkpoint 2: run the benchmark through Downshift (learn once, then cheap model + skill).

Run:  python -m scripts.run_downshift --reset-skills     # start with no skills, learn as it goes
      python -m scripts.run_downshift                    # reuse skills already promoted
      python -m scripts.run_downshift --split holdout
"""
import argparse
import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from downshift import config, db, schema, scorer, skills
from downshift.answer import answer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all", choices=["all", "gate", "holdout"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--reset-skills", action="store_true")
    args = ap.parse_args()

    c = db.client()
    adb, data = db.app_db(c), db.data_coll(c)
    snap = schema.latest(adb.schema_registry, config.DATA_COLLECTION)
    if not snap:
        raise SystemExit("no schema snapshot: run python -m scripts.setup_db first")
    schema_text = schema.schema_for_prompt(snap["fields"])
    if args.reset_skills:
        n = adb.skills.delete_many({}).deleted_count
        print(f"removed {n} skills")

    q = {} if args.split == "all" else {"split": args.split}
    cases = list(adb.test_cases.find(q, {"_id": 0}).sort("caseId", 1))
    if args.limit:
        cases = cases[: args.limit]
    batch_id = "ds-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    print(f"batch {batch_id}: {len(cases)} questions")

    records = []
    for case in cases:
        r = answer(adb, data, case["question"], schema_text, batch_id=batch_id,
                   family=case["family"], case_id=case["caseId"])
        passed, reason = scorer.score(r["rows"], case)
        records.append({"caseId": case["caseId"], "family": case["family"], "split": case["split"],
                        "path": r["path"], "cost": r["cost"], "passed": passed, "reason": reason,
                        "skill": r["skill"], "params": r.get("params"), "trace": r["trace"]})
        print(f"  {'PASS' if passed else 'fail'} {case['caseId']:34} {r['path']:5} ${r['cost']:.5f}  "
              f"{r['skill'] or ''}  {'' if passed else reason[:60]}")

    n = len(records)
    ok = sum(r["passed"] for r in records)
    cost = sum(r["cost"] for r in records)
    paths = Counter(r["path"] for r in records)
    print(f"\nDownshift: accuracy {ok}/{n} ({ok / max(n, 1):.0%}), total ${cost:.4f}, ${cost / max(n, 1):.5f}/question")
    print("paths: " + ", ".join(f"{p}={k}" for p, k in paths.most_common()))
    fam = defaultdict(lambda: [0, 0])
    for r in records:
        fam[r["family"]][0] += r["passed"]
        fam[r["family"]][1] += 1
    for f, (a, b) in sorted(fam.items()):
        print(f"  {f:32} {a}/{b}")
    print("\nskills now live:")
    for s in skills.promoted(adb.skills):
        print(skills.card(s))

    out = Path("results")
    out.mkdir(exist_ok=True)
    (out / f"downshift_{batch_id}.json").write_text(json.dumps(records, indent=2, default=str))
    print(f"\nsaved results/downshift_{batch_id}.json")


if __name__ == "__main__":
    main()
