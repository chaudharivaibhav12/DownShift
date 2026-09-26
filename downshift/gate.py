"""Promotion gate: a candidate skill goes live only if the cheap model can use it to answer every test question."""
from bson import json_util

from . import config, ledger, llm, nl2mql, prompts, skills
from datetime import date


def canonical(rows: list[dict]) -> list[str]:
    """Order-insensitive fingerprint of a result (the template fixes ordering itself)."""
    return sorted(json_util.dumps(r, sort_keys=True) for r in rows)


def fill(model: str, question: str, candidates: list[dict]) -> tuple[llm.LLMResult, dict | None, str | None]:
    """Ask `model` to pick a skill and fill its params. Returns (llm result, {"skillId","params"} or None, error)."""
    system = prompts.SELECT_AND_FILL.format(today=date.today().isoformat(),
                                            skills=prompts.skills_block(candidates))
    res = llm.chat(model, system, question, max_tokens=400)
    if res.error:
        return res, None, f"llm: {res.error}"
    try:
        obj = json_util.loads(llm.extract_json_text(res.text))
        if not isinstance(obj, dict):
            raise ValueError("expected a JSON object")
        return res, obj, None
    except Exception as e:  # noqa: BLE001
        return res, None, f"parse: {e}"


def run_gate(adb, data, skill: dict, tests: list[dict], model: str | None = None, required: float | None = None) -> dict:
    """tests: [{question, expected: canonical rows}]. Promotes or rejects the skill; returns the report."""
    model = model or config.MODELS["cheap"]
    required = config.GATE_PASS_RATE if required is None else required
    passed, failures, passes, cost = 0, [], [], 0.0
    for t in tests:
        res, obj, err = fill(model, t["question"], [skill])
        cost += res.cost_usd
        ok = False
        if obj is not None:
            if obj.get("skillId") != skill["skillId"]:
                err = f"picked {obj.get('skillId')!r}"
            else:
                try:
                    pipeline, _ = skills.render(skill, obj.get("params") or {})
                    rows, _ = nl2mql.run_pipeline(data, pipeline)
                    ok = canonical(rows) == t["expected"]
                    err = None if ok else "different result"
                except Exception as e:  # noqa: BLE001
                    err = f"{type(e).__name__}: {e}"
        ledger.log_run(adb, mode="gate", path="gate", family=skill["skillId"], model=res.model, cost=res.cost_usd,
                       tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms, passed=ok,
                       skill=f"{skill['skillId']}@v{skill['version']}")
        if ok:
            passed += 1
            passes.append({"question": t["question"], "params": obj.get("params") or {}})
        else:
            failures.append({"question": t["question"], "error": err, "modelOutput": res.text[:300]})

    total = len(tests)
    report = {"passed": passed, "total": total, "model": model, "costUsd": round(cost, 6), "failures": failures[:5], "passes": passes[:5]}
    if total and passed / total >= required:
        skills.promote(adb.skills, skill, report)
        ledger.event(adb, "skill_promoted", skill=skill["skillId"], version=skill["version"], passed=passed, total=total)
    else:
        skills.reject(adb.skills, skill, report)
        ledger.event(adb, "skill_rejected", skill=skill["skillId"], version=skill["version"], passed=passed, total=total)
    return report
