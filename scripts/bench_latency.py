"""Measure cheap-model latency per OpenRouter provider-routing option, on our real SELECT_AND_FILL prompt.

Run:  python -m scripts.bench_latency              # cheap model, 5 calls per option (~$0.0005 total)
      python -m scripts.bench_latency --model mid --n 3
Then put the winner in .env, e.g.  PROVIDER_SORT=latency   (or CHEAP_MODEL=meta-llama/llama-3.1-8b-instruct:nitro)
"""
import argparse
import statistics
from datetime import date

from bson import json_util

from downshift import config, db, llm, prompts, skills

QUESTION = "By purchase method, what fraction of 2013 sales used a coupon (the Denver store)?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="cheap", choices=["cheap", "mid"])
    ap.add_argument("--n", type=int, default=5)
    args = ap.parse_args()
    model = config.MODELS[args.model]
    live = skills.promoted(db.app_db().skills)
    if not live:
        raise SystemExit("No live skills: run python -m scripts.run_downshift --reset-skills first.")
    system = prompts.SELECT_AND_FILL.format(today=date.today().isoformat(), skills=prompts.skills_block(live[:3]))
    base = model.split(":")[0]
    options = [("default", base, "", 0), ("sort=throughput", base, "throughput", 0), (":nitro", base + ":nitro", "", 0),
               ("thru+cap 0.05", base, "throughput", 0.05), (":nitro+cap 0.05", base + ":nitro", "", 0.05)]
    print(f"{args.n} calls each · {model} · prompt ~{len(system) // 4} tokens\n")
    print(f"{'option':16} {'median ms':>9} {'p90 ms':>7} {'min ms':>7} {'$ / call':>10}  ok")
    for name, m, sort, cap in options:
        lat, cost, ok = [], [], 0
        for _ in range(args.n):
            r = llm.chat(m, system, QUESTION, max_tokens=200, provider_sort=sort, max_price=cap)
            if r.error:
                print(f"  {name}: {r.error[:120]}")
                continue
            lat.append(r.latency_ms)
            cost.append(r.cost_usd)
            try:
                ok += bool(json_util.loads(llm.extract_json_text(r.text)).get("skillId"))
            except Exception:  # noqa: BLE001
                pass
        if lat:
            p90 = sorted(lat)[max(0, int(len(lat) * 0.9) - 1)]
            print(f"{name:16} {statistics.median(lat):9.0f} {p90:7.0f} {min(lat):7.0f} {statistics.mean(cost):10.6f}  {ok}/{len(lat)}")


if __name__ == "__main__":
    main()
