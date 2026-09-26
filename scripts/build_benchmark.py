"""Step 2: generate the benchmark (30 questions, expected answers from reference pipelines) into `test_cases`.

Run:  python -m scripts.build_benchmark            # replaces existing test cases
      python -m scripts.build_benchmark --show     # also prints every question and answer
      python -m scripts.build_benchmark --fresh    # held-out wordings + seed 7 (honest validation, E14)
      python -m scripts.build_benchmark --seed 11  # any other seed
"""
import json
import sys
from collections import Counter
from pathlib import Path

from bson import json_util

from downshift import benchmark, db


def main():
    c = db.client()
    fresh = "--fresh" in sys.argv
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else (7 if fresh else 42)
    cases = benchmark.build_cases(db.data_coll(c), seed=seed, fresh=fresh)

    tc = db.app_db(c).test_cases
    tc.delete_many({})
    tc.insert_many([dict(x) for x in cases])

    out = Path("results")
    out.mkdir(exist_ok=True)
    name = "benchmark_fresh.json" if fresh else "benchmark.json" if seed == 42 else f"benchmark_seed{seed}.json"
    (out / name).write_text(json_util.dumps(cases, indent=2))

    by = Counter((x["family"], x["split"]) for x in cases)
    print(f"stored {len(cases)} test cases in downshift.test_cases (copy in results/{name}; "
          f"seed {seed}, {'FRESH held-out wordings' if fresh else 'tuning wordings'})")
    for fam in benchmark.FAMILIES:
        print(f"  {fam:32} gate={by[(fam, 'gate')]:2}  holdout={by[(fam, 'holdout')]:2}")

    if "--show" in sys.argv:
        for x in cases:
            print(f"\n[{x['caseId']}] ({x['split']}) {x['question']}")
            for r in x["expectedRows"]:
                print(f"    {r['label']}: {r['value']}")


if __name__ == "__main__":
    main()
