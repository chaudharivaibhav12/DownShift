"""Offline test of schema repair: learn skills, rename storeLocation, repair, answer again.
Run: python -m tests.offline_schema_repair
"""
import sys

import tests.offline_skill_engine as base  # learns the 3 skills and runs the benchmark once
from downshift import repair, skills, config, schema
import scripts.run_downshift as rd

adb, data = base.adb, base.data
before = {s["skillId"]: s["version"] for s in skills.promoted(adb.skills)}

# the demo moment: rename a field everywhere
res = data.update_many({"storeLocation": {"$exists": True}}, {"$rename": {"storeLocation": "store_location"}})
print(f"\nrenamed storeLocation in {res.modified_count} documents")

r = repair.handle_schema_change(adb, data)
print("changed:", r["changed"])
print("flagged:", r["flagged"])
for rep in r["repairs"]:
    print("repair:", {k: rep.get(k) for k in ("skill", "from", "to", "ok", "gate", "error", "note")})

assert set(r["changed"]) >= {"storeLocation", "store_location"}, r["changed"]
assert len(r["flagged"]) == 3, "all three skills read storeLocation"
assert all(rep["ok"] for rep in r["repairs"]), r["repairs"]
after = {s["skillId"]: s for s in skills.promoted(adb.skills)}
for sid, v in before.items():
    assert after[sid]["version"] == v + 1 and "store_location" in after[sid]["fieldsUsed"], after[sid]
events = [e["type"] for e in adb.events.find().sort("ts", 1)]
assert "schema_changed" in events and "skill_flagged" in events and "skill_repaired" in events

# answers after repair should use the repaired skills on the cheap path and still be right
sys.argv = ["run_downshift"]
rd.main()
recent = list(adb.ledger.find({"meta.mode": "downshift"}).sort("ts", -1).limit(30))
assert not any(d["path"] in ("learn", "frontier") for d in recent), "no re-learning after repair"

# nothing changed -> handler is a no-op
assert repair.handle_schema_change(adb, data)["changed"] == []
# a repair that doesn't really fix things must be refused, and answers fall back to the frontier
data.update_many({"store_location": {"$exists": True}}, {"$rename": {"store_location": "shop"}})
r2 = repair.handle_schema_change(adb, data)   # the stub model only knows storeLocation -> store_location
assert r2["repairs"] and not any(rep["ok"] for rep in r2["repairs"]), r2["repairs"]
print("bad repair refused:", r2["repairs"][0]["error"])
from downshift.answer import answer
q = next(c for c in base.cases if c["family"] == "top_stores_by_revenue")
out = answer(adb, data, q["question"], schema.schema_for_prompt(schema.latest(adb.schema_registry, config.DATA_COLLECTION)["fields"]))
# a refused repair must not wedge the system: skills go "broken" (off the cheap path), nothing stays "flagged",
# and new questions may learn again instead of being stuck on frontier-only forever
assert adb.skills.count_documents({"status": "flagged"}) == 0
assert adb.skills.count_documents({"status": "broken"}) == 3
assert out["path"] == "learn", out["trace"]
print("after refused repair:", out["path"], "| broken:", adb.skills.count_documents({"status": "broken"}))

# reverting the schema (shop -> store_location, which the broken skills read) retries them and brings them back
data.update_many({"shop": {"$exists": True}}, {"$rename": {"shop": "store_location"}})
r3 = repair.handle_schema_change(adb, data)
retried = [rep for rep in r3["repairs"] if rep.get("from") is not None]
assert len(retried) >= 3 and all(rep["ok"] for rep in retried), r3["repairs"]
assert adb.skills.count_documents({"status": "broken"}) == 0
assert adb.skills.count_documents({"status": "flagged"}) == 0
print("after revert:", [f"{rep['skill']} -> v{rep['to']}" for rep in r3["repairs"]])

print("\nALL SCHEMA-REPAIR CHECKS PASSED")
