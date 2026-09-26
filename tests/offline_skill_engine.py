"""Offline end-to-end test of the skill engine (checkpoint 2) with mongomock and a scripted stand-in model.

The stand-in 'frontier' writes correct pipelines and templates; the 'cheap' model fills params but makes
occasional mistakes (to exercise escalation to 'mid'). No network needed.
Run: python -m tests.offline_skill_engine
"""
import random
import re
import sys
from datetime import timedelta

import mongomock
from bson import json_util

from downshift import benchmark, config, db, gate, learn, llm, nl2mql, schema, skills
from tests.local_smoke_data import make_data

client = mongomock.MongoClient()
db.client = lambda: client
data, adb = db.data_coll(client), db.app_db(client)
make_data(data)
for name in ("skills", "test_cases", "schema_registry", "events", "runs", "ledger"):
    adb.create_collection(name)
snap = schema.snapshot(adb.schema_registry, data, config.DATA_COLLECTION)
cases = benchmark.build_cases(data)
adb.test_cases.insert_many([dict(x) for x in cases])

# registry: question -> (family, query params)
REG = {c["question"]: (c["family"], dict(c["params"])) for c in cases}

def iso(d): return d.strftime("%Y-%m-%d")

def skill_params(fam, p):
    if fam == "top_stores_by_revenue":
        return {"start": iso(p["start"]), "end": iso(p["end"]), "limit": p["limit"]}
    if fam == "top_items_by_tag_in_store":
        return {"store": p["store"], "tag": p["tag"], "limit": p["limit"]}
    out = {"start": f"{p['year']}-01-01", "end": f"{p['year'] + 1}-01-01"}
    if p.get("store"):
        out["store"] = p["store"]
    return out

TEMPLATES = {
    "top_stores_by_revenue": ([
        {"$match": {"saleDate": {"$gte": "{{start}}", "$lt": "{{end}}"}}}, {"$unwind": "$items"},
        {"$group": {"_id": "$storeLocation", "revenue": {"$sum": {"$multiply": ["$items.price", "$items.quantity"]}}}},
        {"$sort": {"revenue": -1, "_id": 1}}, {"$limit": "{{limit}}"}],
        {"start": {"type": "date", "description": "first day, inclusive"}, "end": {"type": "date", "description": "day after the period, exclusive"},
         "limit": {"type": "int", "description": "how many stores", "min": 1, "max": 50}}),
    "top_items_by_tag_in_store": ([
        {"$match": {"storeLocation": "{{store}}"}}, {"$unwind": "$items"}, {"$match": {"items.tags": "{{tag}}"}},
        {"$group": {"_id": "$items.name", "units": {"$sum": "$items.quantity"}}}, {"$sort": {"units": -1, "_id": 1}},
        {"$limit": "{{limit}}"}],
        {"store": {"type": "string", "description": "store location"}, "tag": {"type": "string", "description": "item tag"},
         "limit": {"type": "int", "description": "how many items"}}),
    "coupon_rate_by_purchase_method": ([
        {"$match": {"saleDate": {"$gte": "{{start}}", "$lt": "{{end}}"}, "storeLocation": "{{store}}"}},
        {"$group": {"_id": "$purchaseMethod", "rate": {"$avg": {"$cond": ["$couponUsed", 1, 0]}}}}, {"$sort": {"_id": 1}}],
        {"start": {"type": "date", "description": "Jan 1 of the year, inclusive"}, "end": {"type": "date", "description": "Jan 1 of next year, exclusive"},
         "store": {"type": "string", "optional": True, "description": "store location; omit for all stores"}}),
}

rng = random.Random(7)
ctx = benchmark.data_context(data)
calls = {"frontier": 0, "mid": 0, "cheap": 0}

def concrete(fam, p):
    pipe = benchmark.FAMILIES[fam]["pipeline"](dict(p))
    if fam == "top_items_by_tag_in_store":
        pipe[-1] = {"$limit": p["limit"]}
    return pipe

def fake_chat(model, system, user, max_tokens=1500, retries=2):
    tier = next(k for k, v in config.MODELS.items() if v == model)
    calls[tier] = calls.get(tier, 0) + 1
    cost = {"frontier": 0.02, "mid": 0.002, "cheap": 0.0002, "auto": 0.01}[tier]
    R = lambda obj: llm.LLMResult(text=json_util.dumps(obj), model=model, cost_usd=cost, tokens_in=400, tokens_out=150, latency_ms=500)

    if "TASK: REPAIR" in user:
        old = re.search(r"Old template \(Extended JSON.*?\n(.*?)\n\nRewrite", user, re.S).group(1)
        fixed = old.replace('"$storeLocation"', '"$store_location"').replace('"storeLocation"', '"store_location"')
        return llm.LLMResult(text=json_util.dumps({"note": "storeLocation is now store_location"})[:-1]
                             + ', "template": ' + fixed + "}", model=model, cost_usd=cost)

    if "TASK: GENERALIZE" in user:
        q = re.search(r"^Question: (.*)$", user, re.M).group(1)
        fam, p = REG[q]
        template, params = TEMPLATES[fam]
        tests = []
        for i in range(8):
            tp = benchmark.FAMILIES[fam]["params"](rng, ctx, i)
            if fam == "top_items_by_tag_in_store":
                tp["limit"] = 3
            tq = benchmark.FAMILIES[fam]["templates"][(i + 3) % 10].format(**tp) + f" (t{i})"
            qp = {k: v for k, v in tp.items() if k not in ("period", "scope")}
            REG[tq] = (fam, qp)
            tests.append({"question": tq, "params": skill_params(fam, qp)})
        return R({"skillId": fam, "intent": f"Answer {fam.replace('_', ' ')} questions",
                  "params": params, "template": template, "originalParams": skill_params(fam, p), "testQuestions": tests})

    if "TASK: SELECT_AND_FILL" in system:
        fam, p = REG[user]
        if f"skillId: {fam}" not in system:
            return R({"skillId": None})
        sp = skill_params(fam, p)
        if tier == "cheap" and rng.random() < 0.15:     # cheap model slips sometimes
            sp = dict(sp); sp.pop(next(iter(sp)))        # forgets a required param
        return R({"skillId": fam, "params": sp})

    # concrete pipeline (nl2mql); a good frontier model reads the current schema
    fam, p = REG[user]
    text = json_util.dumps({"pipeline": concrete(fam, p)})
    if "store_location" in system:
        text = text.replace('"$storeLocation"', '"$store_location"').replace('"storeLocation"', '"store_location"')
    return llm.LLMResult(text=text, model=model, cost_usd=cost, tokens_in=400, tokens_out=150, latency_ms=500)

llm.chat = fake_chat
nl2mql.llm.chat = fake_chat

# 1. unit checks on skills.py
t = TEMPLATES["coupon_rate_by_purchase_method"][0]
assert "storeLocation" not in skills.substitute(t, {"start": 1, "end": 2, "store": None})[0]["$match"]
assert skills.fields_used(TEMPLATES["top_stores_by_revenue"][0]) == ["items", "items.price", "items.quantity", "saleDate", "storeLocation"]
try:
    skills.validate_params(TEMPLATES["top_stores_by_revenue"][1], {"start": "2016-01-01", "end": "2016-02-01", "limit": 999}); raise SystemExit("range check failed")
except skills.ParamError:
    pass

# 2. full Downshift run over the benchmark, starting with no skills
sys.argv = ["run_downshift"]
import scripts.run_downshift as rd
rd.main()

paths = [d["path"] for d in adb.ledger.find({"meta.mode": "downshift"})]
live = skills.promoted(adb.skills)
assert len(live) == 3, f"expected 3 promoted skills, got {len(live)}"
assert calls["cheap"] > 0 and calls["frontier"] >= 6
print(f"\nmodel calls: {calls}")
print("ALL SKILL-ENGINE CHECKS PASSED")
