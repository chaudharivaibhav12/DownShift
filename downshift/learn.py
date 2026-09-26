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
        return res, skills.loads_model_json(llm.extract_json_text(res.text)), None
    except Exception as e:  # noqa: BLE001
        return res, None, f"parse: {e}"


def learn(adb, data, question: str, schema_text: str, model: str | None = None,
          batch_id: str | None = None, family: str = "?", min_tests: int = 5, make_skill: bool = True,
          replaces: str | None = None) -> dict:
    """replaces: skillId of a live skill that was too narrow for this question; the new skill takes its name, so
    promoting it retires the narrow version instead of leaving both live."""
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

    draft = {"skillId": replaces or spec.get("skillId") or "skill", "params": params,
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
        fieldsUsed=skills.fields_used(template, skills.known_fields(schema_text)),
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

    # 6. rejected? reflect on the failing vs passing traces and try once more with a better description
    if skill["status"] == "rejected" and config.REFLECT_ON_REJECT:
        skill2, cost2, err = reflect(adb, data, skill, tests, report, model, batch_id=batch_id)
        out["cost"] += cost2
        if skill2:
            out["skill"] = skill2
            out["steps"].append(f"reflected -> v{skill2['version']} {skill2['status']}")
        elif err:
            out["steps"].append(f"reflect failed: {err}")
    return out


def reflect(adb, data, skill: dict, tests: list[dict], report: dict, model: str,
            batch_id: str | None = None) -> tuple[dict | None, float, str | None]:
    """Contrastive reflection: the frontier reads the gate's winning and losing traces and rewrites the
    cheap-facing part of the skill (intent, param descriptions, examples). Template unchanged. Re-gated.
    Returns (new skill or None, cost, error)."""
    fmt = lambda xs: "\n".join(json_util.dumps(x) for x in xs) or "(none)"  # noqa: E731
    user = prompts.REFLECT.format(skillId=skill["skillId"], intent=skill["intent"],
                                  params=json_util.dumps(skill["params"]), examples=json_util.dumps(skill["examples"]),
                                  passes=fmt(report.get("passes", [])), failures=fmt(report.get("failures", [])))
    with trace.timed() as t:
        res = llm.chat(model, "You are precise and reply with JSON only.", user, max_tokens=1500)
    ledger.log_run(adb, mode="downshift", path="learn", family=skill["skillId"], model=res.model, cost=res.cost_usd,
                   tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms, batch_id=batch_id,
                   extra={"step": "reflect"})
    try:
        if res.error:
            raise ValueError(res.error)
        spec = json_util.loads(llm.extract_json_text(res.text))
        # only descriptions may change; names, types, optional flags and values are the skill's contract
        params = {k: {**v, "description": (spec.get("params") or {}).get(k, {}).get("description", v.get("description", ""))}
                  for k, v in skill["params"].items()}
    except Exception as e:  # noqa: BLE001
        trace.step("frontier model · reflect on gate failures", "frontier", ms=t["ms"], cost=res.cost_usd, ok=False, detail=str(e)[:120])
        return None, res.cost_usd, f"reflect: {e}"
    trace.step("frontier model · reflect on gate failures", "frontier", ms=t["ms"], cost=res.cost_usd, model=res.model,
               detail=spec.get("note", "")[:120])

    skill2 = skills.new_skill(
        adb.skills, skill["skillId"],
        intent=spec.get("intent") or skill["intent"],
        examples=spec.get("examples") or skill["examples"],
        params=params,
        templateJson=skill["templateJson"],
        fieldsUsed=skill["fieldsUsed"],
        createdBy=model,
        gateTests=tests,
        reflectionNote=spec.get("note", ""),
        reflectedFrom=skill["version"],
    )
    ledger.event(adb, "skill_reflected", skill=skill2["skillId"], version=skill2["version"],
                 fromVersion=skill["version"], note=spec.get("note", ""))
    with trace.timed() as t:
        report2 = gate.run_gate(adb, data, skill2, tests)
    trace.step(f"promotion gate · retry × {report2['total']}", "gate", ms=t["ms"], cost=report2["costUsd"],
               ok=skill2["status"] == "promoted", detail=f"{report2['passed']}/{report2['total']} → {skill2['status']}")
    return skill2, res.cost_usd + report2["costUsd"], None
