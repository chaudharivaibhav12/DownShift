"""Step 2: generate the benchmark (30 questions, expected answers from reference pipelines) into `test_cases`.

Run:  python -m scripts.build_benchmark            # replaces existing test cases
      python -m scripts.build_benchmark --show     # also prints every question and answer
"""
import json
import sys
from collections import Counter
from pathlib import Path

from bson import json_util

from downshift import benchmark, db


def main():
    c = db.client()
    cases = benchmark.build_cases(db.data_coll(c))

    tc = db.app_db(c).test_cases
    tc.delete_many({})
    tc.insert_many([dict(x) for x in cases])

    out = Path("results")
    out.mkdir(exist_ok=True)
    (out / "benchmark.json").write_text(json_util.dumps(cases, indent=2))

    by = Counter((x["family"], x["split"]) for x in cases)
    print(f"stored {len(cases)} test cases in downshift.test_cases (copy in results/benchmark.json)")
    for fam in benchmark.FAMILIES:
        print(f"  {fam:32} gate={by[(fam, 'gate')]:2}  holdout={by[(fam, 'holdout')]:2}")

    if "--show" in sys.argv:
        for x in cases:
            print(f"\n[{x['caseId']}] ({x['split']}) {x['question']}")
            for r in x["expectedRows"]:
                print(f"    {r['label']}: {r['value']}")


if __name__ == "__main__":
    main()
