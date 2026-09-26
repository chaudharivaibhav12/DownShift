"""Offline smoke test: mongomock + synthetic sales data + a stub LLM. No network, no Atlas.
Run: python -m tests.local_smoke
"""
import os, tempfile
os.environ["DOWNSHIFT_RESULTS_DIR"] = tempfile.mkdtemp(prefix="downshift-test-")  # stub runs never land in results/
import random, sys
from datetime import datetime, timedelta, timezone
from bson import json_util, Decimal128
import mongomock

from downshift import benchmark, db, llm, nl2mql, schema, scorer, config
import scripts.setup_db as setup_db
import scripts.run_baselines as rb

from tests.local_smoke_data import make_data

client = mongomock.MongoClient()
db.client.cache_clear() if hasattr(db.client, "cache_clear") else None
db.client = lambda: client  # patch
make_data(db.data_coll(client))

# setup
setup_db.main()

# benchmark
cases = benchmark.build_cases(db.data_coll(client))
adb = db.app_db(client); adb.test_cases.insert_many([dict(x) for x in cases])
print(f"\nbuilt {len(cases)} cases; example: {cases[0]['question']} -> {cases[0]['expectedRows']}")
assert len(cases) == 30

# stub LLM: "frontier" returns the reference pipeline (as Extended JSON text), "cheap" makes mistakes
by_q = {x["question"]: x for x in cases}
def fake_chat(model, system, user, max_tokens=1500, retries=2):
    case = by_q[user]
    p = benchmark.FAMILIES[case["family"]]["pipeline"](dict(case["params"]))
    if case["family"] == "top_items_by_tag_in_store":
        p[-1] = {"$limit": case["params"]["limit"]}
    if model == config.MODELS["cheap"]:
        if case["family"] == "top_items_by_tag_in_store":
            p = [s for s in p if "$sort" not in s]          # forgets to sort
        elif case["family"] == "coupon_rate_by_purchase_method":
            return llm.LLMResult(text="Sure! Here is the pipeline you asked for.", model=model, cost_usd=0.00001)
    text = "```json\n" + json_util.dumps({"pipeline": p}) + "\n```"
    cost = 0.02 if model == config.MODELS["frontier"] else 0.00002
    return llm.LLMResult(text=text, model=model, cost_usd=cost, tokens_in=500, tokens_out=200, latency_ms=900)
llm.chat = fake_chat
nl2mql.llm.chat = fake_chat

sys.argv = ["run_baselines", "--modes", "cheap,frontier", "--workers", "1"]
rb.main()

# scorer unit checks
case = {"expectedRows": [{"label": "Denver", "value": 100.0}, {"label": "Austin", "value": 50.0}], "ordered": True}
assert scorer.score([{"_id": "Denver", "total": Decimal128("100.004")}, {"_id": "Austin", "t": 50}], case)[0]
assert not scorer.score([{"_id": "Austin", "t": 50}, {"_id": "Denver", "total": 100}], case)[0]
rate = {"expectedRows": [{"label": "Online", "value": 0.2}], "ordered": False, "rate": True}
assert scorer.score([{"method": "Online", "pct": 20.1}], rate)[0]
try:
    nl2mql.check_safe([{"$match": {}}, {"$out": "x"}]); raise SystemExit("safety check failed")
except nl2mql.UnsafePipeline:
    pass
print("\nALL SMOKE CHECKS PASSED")
