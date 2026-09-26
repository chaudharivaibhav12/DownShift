"""Learn path: the frontier model answers a new kind of question, then turns its pipeline into a skill.

1. Frontier writes a concrete pipeline and we answer the user with it.
2. Frontier generalizes it into a template with typed params + 8 test questions.
3. Self-check: the template with the original params must reproduce the answer exactly.
4. Test answers come from the template, and the gate checks the cheap model can fill the params.
"""
from bson import json_util

from . import config, gate, ledger, llm, nl2mql, prompts, skills, trace


def _generalize(model, question, pipeline, schema_text):
    user = prompts.GENERALIZE.format(collection=config.DATA_COLLECTION, schema=schema_text,
                                     question=question, pipeline=json_util.dumps(pipeline))
    res = llm.chat(model, "You are precise and reply with JSON only.", user, max_tokens=3000)
    if res.error:
        return res, None, f"llm: {res.error}"
    try:
        return res, json_util.loads(llm.extract_json_text(res.text)), None
    except Exception as e:  # noqa: BLE001
        return res, None, f"parse: {e}"


def learn(adb, data, question: str, schema_text: str, model: str | None = None,
          batch_id: str | None = None, family: str = "?", min_tests: int = 5, make_skill: bool = True) -> dict:
    model = model or config.MODELS["frontier"]
    out = {"rows": None, "cost": 0.0, "skill": None, "error": None, "steps": []}

    # 1. answer the question
    with trace.timed() as t:
        res, pipeline, err = nl2mql.generate(model, question, schema_text)
    out["cost"] += res.cost_usd
    trace.step("frontier model · write pipeline", "frontier", ms=t["ms"], cost=res.cost_usd, model=res.model, ok=not err, detail=err)
    ledger.log_run(adb, mode="downshift", path="learn", family=family, model=res.model, cost=res.cost_usd,
                   tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms, batch_id=batch_id)
    if err:
        out["error"] = err
        return out
    try:
        rows, db_ms = nl2mql.run_pipeline(data, pipeline)
        trace.step("aggregate on Atlas", "db", ms=db_ms, detail=" → ".join(next(iter(st)) for st in pipeline))
    except Exception as e:  # noqa: BLE001
        out["error"] = f"run: {e}"
        trace.step("aggregate on Atlas", "db", ok=False, detail=str(e)[:120])
        return out
    out["rows"] = rows
    out["pipeline"] = pipeline
    out["steps"].append("answered")
    if not make_skill:
        return out

    # 2. generalize
    with trace.timed() as t:
        res, spec, err = _generalize(model, question, pipeline, schema_text)
    out["cost"] += res.cost_usd
    trace.step("frontier model · generalize into skill", "frontier", ms=t["ms"], cost=res.cost_usd, model=res.model, ok=not err, detail=err)
    ledger.log_run(adb, mode="downshift", path="learn", family=family, model=res.model, cost=res.cost_usd,
                   tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms, batch_id=batch_id,
                   extra={"step": "generalize"})
    if err:
        out["error"] = f"generalize {err}"
        return out
    try:
        template = spec["template"]
        params = spec["params"]
        used = skills.placeholders(template)
        if used - set(params):
            raise ValueError(f"template uses undeclared params {sorted(used - set(params))}")
        params = {k: v for k, v in params.items() if k in used}  # drop params the template never uses
        nl2mql.check_safe(template)
    except Exception as e:  # noqa: BLE001
        out["error"] = f"bad skill spec: {e}"
        return out

    draft = {"skillId": spec.get("skillId") or "skill", "params": params,
             "templateJson": json_util.dumps(template)}

    # 3. self-check against the answer we just gave
    try:
        p0, _ = skills.render(draft, spec.get("originalParams") or {})
        rows0, _ = nl2mql.run_pipeline(data, p0)
        if gate.canonical(rows0) != gate.canonical(rows):
            raise ValueError("template with originalParams does not reproduce the answer")
    except Exception as e:  # noqa: BLE001
        out["error"] = f"self-check: {e}"
        return out
    out["steps"].append("self-check ok")
    trace.step("self-check · template reproduces answer", "check")

    # 4. tests with expected answers from the template
    tests = []
    for t in spec.get("testQuestions") or []:
        try:
            p, _ = skills.render(draft, t.get("params") or {})
            r, _ = nl2mql.run_pipeline(data, p)
            if r:
                tests.append({"question": t["question"], "params": t.get("params") or {}, "expected": gate.canonical(r)})
        except Exception:  # noqa: BLE001 - drop broken test questions
            continue
    if len(tests) < min_tests:
        out["error"] = f"only {len(tests)} usable test questions"
        return out

    skill = skills.new_skill(
        adb.skills, draft["skillId"],
        intent=spec.get("intent", ""),
        examples=[question] + [t["question"] for t in tests[:4]],
        params=params,
        templateJson=draft["templateJson"],
        fieldsUsed=skills.fields_used(template),
        createdBy=model,
        gateTests=tests,
    )
    ledger.event(adb, "skill_candidate", skill=skill["skillId"], version=skill["version"])
    out["steps"].append(f"candidate {skill['skillId']} v{skill['version']}")

    # 5. gate
    with trace.timed() as t:
        report = gate.run_gate(adb, data, skill, tests)
    trace.step(f"promotion gate · cheap model × {report['total']}", "gate", ms=t["ms"], cost=report["costUsd"],
               ok=skill["status"] == "promoted", detail=f"{report['passed']}/{report['total']} → {skill['status']}")
    out["cost"] += report["costUsd"]
    out["skill"] = skill
    out["steps"].append(f"gate {report['passed']}/{report['total']} -> {skill['status']}")
    return out
