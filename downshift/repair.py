"""Schema repair: notice a schema change, flag the skills it breaks, have the frontier fix them, re-verify, re-gate.

Flow (handle_schema_change):
  1. re-snapshot the schema -> changedFields
  2. flag promoted skills whose fieldsUsed touch a changed field (flagged skills are not used by the cheap path)
  3. for each flagged skill: frontier rewrites the template for the new schema
  4. verify: with each stored test's params, the new template must reproduce the answer the old skill gave
     (a rename or move changes the shape, not the data, so the answers should be identical)
  5. gate with the cheap model -> promote as a new version; the old version is retired
"""
from datetime import datetime, timezone

from bson import json_util

from . import config, gate, ledger, llm, nl2mql, prompts, schema, skills


def touches(fields_used: list[str], changed: list[str]) -> bool:
    for f in fields_used:
        for c in changed:
            if f == c or f.startswith(c + ".") or c.startswith(f + "."):
                return True
    return False


def flag_skills(adb, changed: list[str]) -> list[dict]:
    hit = [s for s in skills.promoted(adb.skills) if touches(s.get("fieldsUsed", []), changed)]
    for s in hit:
        adb.skills.update_one({"_id": s["_id"]}, {"$set": {"status": "flagged", "flaggedFor": changed}})
        s["status"] = "flagged"
        ledger.event(adb, "skill_flagged", skill=s["skillId"], version=s["version"], fields=changed)
    return hit


def _label(canonical: list[str] | None) -> str:
    """Short preview of a result for the console: the first row's name and number, e.g. "Austin 60,436"."""
    if not canonical:
        return "—"
    try:
        row = json_util.loads(sorted(canonical)[0])
        name = next((str(v) for v in row.values() if isinstance(v, str)), "")
        n = next((v for v in row.values() if isinstance(v, (int, float)) and not isinstance(v, bool)), None)
        val = "" if n is None else (f"{n:,.0f}" if abs(n) >= 100 else f"{n:.2f}")
        more = f" +{len(canonical) - 1}" if len(canonical) > 1 else ""
        return (f"{name} {val}".strip() or "?") + more
    except Exception:  # noqa: BLE001
        return "?"


def repair_skill(adb, data, skill: dict, snap: dict, model: str | None = None) -> dict:
    model = model or config.MODELS["frontier"]
    out = {"skill": skill["skillId"], "from": skill["version"], "ok": False, "cost": 0.0, "error": None}
    user = prompts.REPAIR.format(
        collection=config.DATA_COLLECTION, changed=", ".join(snap["changedFields"]),
        schema=schema.schema_for_prompt(snap["fields"]), intent=skill["intent"],
        params=json_util.dumps(skill["params"]), template=skill["templateJson"])
    res = llm.chat(model, "You are precise and reply with JSON only.", user, max_tokens=2500)
    out["cost"] += res.cost_usd
    ledger.log_run(adb, mode="repair", path="repair", family=skill["skillId"], model=res.model, cost=res.cost_usd,
                   tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms)
    if res.error:
        out["error"] = f"llm: {res.error}"
        return out
    try:
        obj = json_util.loads(llm.extract_json_text(res.text))
        template = obj["template"]
        nl2mql.check_safe(template)
        missing = set(skill["params"]) - skills.placeholders(template)
        if missing:
            raise ValueError(f"repair dropped params {sorted(missing)}")
    except Exception as e:  # noqa: BLE001
        out["error"] = f"bad repair: {e}"
        return out

    draft = {**skill, "templateJson": json_util.dumps(template)}
    # verify against what the old skill answered, using the stored test params
    tests, mismatches, equivalence = [], 0, []
    for t in skill.get("gateTests", []):
        try:
            p, _ = skills.render(draft, t.get("params") or {})
            rows, _ = nl2mql.run_pipeline(data, p)
            got = gate.canonical(rows)
        except Exception:  # noqa: BLE001
            got = None
        same = got == t["expected"]
        if not same:
            mismatches += 1
        equivalence.append({"question": t["question"], "same": same, "before": _label(t["expected"]),
                            "after": _label(got), "rows": len(got or [])})
        tests.append({**t, "expected": got if got is not None else t["expected"]})
    out["equivalence"] = equivalence
    out["templateBefore"] = skill["templateJson"]
    out["templateAfter"] = json_util.dumps(template)
    if not tests or mismatches:
        out["error"] = f"new template changes {mismatches}/{len(tests)} answers"
        ledger.event(adb, "repair_failed", skill=skill["skillId"], reason=out["error"])
        return out

    new = skills.new_skill(
        adb.skills, skill["skillId"], intent=skill["intent"], examples=skill.get("examples", []),
        params=skill["params"], templateJson=draft["templateJson"],
        fieldsUsed=skills.fields_used(template), createdBy=model, gateTests=tests,
        repairNote=obj.get("note", ""), repairedFrom=skill["version"])
    report = gate.run_gate(adb, data, new, tests)
    out["cost"] += report["costUsd"]
    out.update(to=new["version"], ok=new["status"] == "promoted", gate=f"{report['passed']}/{report['total']}",
               note=obj.get("note", ""))
    if out["ok"]:
        adb.skills.update_one({"_id": skill["_id"]}, {"$set": {"status": "retired"}})
        ledger.event(adb, "skill_repaired", skill=skill["skillId"], version=new["version"], note=out["note"])
    else:
        out["error"] = f"gate {out['gate']}"
    return out


def handle_schema_change(adb, data) -> dict:
    """Run the whole repair flow once. Safe to call when nothing changed.

    Progress is written to the `repairs` collection (stage: detected -> flagged -> repairing -> done) so the
    console can show each step as it happens.
    """
    snap = schema.snapshot(adb.schema_registry, data, config.DATA_COLLECTION)
    result = {"version": snap["version"], "changed": snap["changedFields"], "flagged": [], "repairs": []}
    if not snap["changedFields"]:
        return result
    ledger.event(adb, "schema_changed", version=snap["version"], fields=snap["changedFields"])
    rid = adb.repairs.insert_one({"ts": datetime.now(timezone.utc), "stage": "detected",
                                  "schemaVersion": snap["version"], "changed": snap["changedFields"],
                                  "flagged": [], "results": []}).inserted_id
    flagged = flag_skills(adb, snap["changedFields"])
    result["flagged"] = [f"{s['skillId']}@v{s['version']}" for s in flagged]
    adb.repairs.update_one({"_id": rid}, {"$set": {"stage": "flagged", "flagged": result["flagged"]}})
    adb.repairs.update_one({"_id": rid}, {"$set": {"stage": "repairing"}})
    for s in flagged:
        rep = repair_skill(adb, data, s, snap)
        result["repairs"].append(rep)
        adb.repairs.update_one({"_id": rid}, {"$push": {"results": rep}})
    adb.repairs.update_one({"_id": rid}, {"$set": {"stage": "done", "doneAt": datetime.now(timezone.utc)}})
    return result
