"""Step 3 (checkpoint 1): run the benchmark with no skills, one model tier at a time.

Every question: model writes a pipeline -> safety check -> run on the data -> score -> log to `ledger`.

Run:  python -m scripts.run_baselines                       # cheap, frontier, auto on all 30
      python -m scripts.run_baselines --modes cheap --limit 5
      python -m scripts.run_baselines --split holdout --workers 2
"""
import argparse
import json
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from bson import json_util

from downshift import config, db, nl2mql, schema, scorer


def run_one(mode: str, case: dict, schema_text: str, data, batch_id: str) -> dict:
    model = config.MODELS[mode]
    res, pipeline, err = nl2mql.generate(model, case["question"], schema_text)
    rows, db_ms, passed, reason = None, 0, False, err
    if pipeline is not None:
        try:
            rows, db_ms = nl2mql.run_pipeline(data, pipeline)
            passed, reason = scorer.score(rows, case)
        except Exception as e:  # noqa: BLE001 - bad pipelines fail in many ways
            reason = f"run: {type(e).__name__}: {str(e)[:200]}"
    return {
        "batchId": batch_id,
        "mode": mode,
        "caseId": case["caseId"],
        "family": case["family"],
        "split": case["split"],
        "question": case["question"],
        "modelRequested": model,
        "modelUsed": res.model,
        "tokensIn": res.tokens_in,
        "tokensOut": res.tokens_out,
        "costUsd": res.cost_usd,
        "latencyMs": res.latency_ms + db_ms,
        "passed": passed,
        "reason": reason if not passed else "ok",
        "pipeline": json_util.dumps(pipeline) if pipeline is not None else None,
        "rawOutput": res.text[:4000],
        "resultPreview": json_util.dumps(rows[:5]) if rows else None,
    }


def log(adb, rec: dict):
    now = datetime.now(timezone.utc)
    adb.ledger.insert_one({
        "ts": now,
        "meta": {"mode": rec["mode"], "family": rec["family"], "model": rec["modelUsed"]},
        "batchId": rec["batchId"], "caseId": rec["caseId"], "path": "baseline",
        "tokensIn": rec["tokensIn"], "tokensOut": rec["tokensOut"], "costUsd": rec["costUsd"],
        "latencyMs": rec["latencyMs"], "passed": rec["passed"],
    })
    adb.runs.insert_one({**rec, "ts": now})


def summarize(records: list[dict], modes: list[str]) -> str:
    fams = sorted({r["family"] for r in records})
    agg = defaultdict(lambda: {"n": 0, "ok": 0, "cost": 0.0, "ms": 0})
    for r in records:
        for key in ((r["mode"], "ALL"), (r["mode"], r["family"])):
            a = agg[key]
            a["n"] += 1
            a["ok"] += r["passed"]
            a["cost"] += r["costUsd"]
            a["ms"] += r["latencyMs"]
    lines = [f"{'mode':9} {'family':32} {'accuracy':>9} {'cost/q ($)':>11} {'total ($)':>10} {'avg ms':>7}"]
    for m in modes:
        for f in ["ALL"] + fams:
            a = agg[(m, f)]
            if not a["n"]:
                continue
            lines.append(f"{m:9} {f:32} {a['ok']:>3}/{a['n']:<3}{a['ok'] / a['n']:>4.0%} "
                         f"{a['cost'] / a['n']:>11.5f} {a['cost']:>10.4f} {a['ms'] // a['n']:>7}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="cheap,frontier,auto")
    ap.add_argument("--split", default="all", choices=["all", "gate", "holdout"])
    ap.add_argument("--limit", type=int, default=0, help="max questions per mode (0 = all)")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for m in modes:
        if m not in config.MODELS:
            raise SystemExit(f"unknown mode {m}; choose from {list(config.MODELS)}")

    c = db.client()
    adb, data = db.app_db(c), db.data_coll(c)
    snap = schema.latest(adb.schema_registry, config.DATA_COLLECTION)
    if not snap:
        raise SystemExit("no schema snapshot: run python -m scripts.setup_db first")
    schema_text = schema.schema_for_prompt(snap["fields"])

    q = {} if args.split == "all" else {"split": args.split}
    cases = list(adb.test_cases.find(q, {"_id": 0}).sort("caseId", 1))
    if not cases:
        raise SystemExit("no test cases: run python -m scripts.build_benchmark first")
    if args.limit:
        cases = cases[: args.limit]

    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    print(f"batch {batch_id}: {len(cases)} questions x {modes}")
    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(run_one, m, x, schema_text, data, batch_id) for m in modes for x in cases]
        for fut in as_completed(futs):
            rec = fut.result()
            log(adb, rec)
            records.append(rec)
            mark = "PASS" if rec["passed"] else "fail"
            print(f"  {mark} {rec['mode']:8} {rec['caseId']:34} ${rec['costUsd']:.5f} {rec['reason'][:70]}")

    table = summarize(records, modes)
    print("\n" + table)
    out = Path("results")
    out.mkdir(exist_ok=True)
    (out / f"baseline_{batch_id}.json").write_text(json.dumps(records, indent=2, default=str))
    (out / f"baseline_{batch_id}.txt").write_text(table)
    print(f"saved results/baseline_{batch_id}.json and .txt; ledger rows tagged batchId={batch_id}")


if __name__ == "__main__":
    main()
