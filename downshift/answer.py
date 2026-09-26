"""The Downshift answer loop.

  question -> shortlist promoted skills -> cheap model picks a skill + fills params -> run
     | fails (bad params, error, empty result)  -> mid model tries the same
     | no skill fits, or mid fails              -> learn path (frontier answers, then makes a skill)
"""
import re

from . import config, gate, learn, ledger, nl2mql, skills, trace

_WORD = re.compile(r"[a-z0-9]+")
STOP = {"the", "a", "an", "of", "in", "for", "by", "to", "and", "what", "which", "me", "show", "give", "top",
        "is", "are", "was", "were", "with", "on", "at", "our", "please", "i", "need", "list", "how"}


def _show(v):
    """Param value for display: dates as YYYY-MM-DD."""
    return v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in STOP and not w.isdigit()}


def shortlist(question: str, all_skills: list[dict], k: int = 3) -> list[dict]:
    """Cheap lexical ranking over intent + examples. (Atlas hybrid search replaces this once the cluster is up.)"""
    q = _tokens(question)
    scored = []
    for s in all_skills:
        vocab = _tokens(s.get("intent", "") + " " + " ".join(s.get("examples", [])))
        score = len(q & vocab) / (len(q | vocab) or 1)
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:k]]


def answer(adb, data, question: str, schema_text: str, batch_id: str | None = None,
           family: str = "?", case_id: str | None = None) -> dict:
    out = {"question": question, "rows": None, "path": None, "cost": 0.0, "skill": None, "trace": []}
    live = skills.promoted(adb.skills)
    with trace.timed() as t:
        candidates = shortlist(question, live) if live else []
    trace.step("skill search", "search", ms=t["ms"], detail=f"{len(candidates)} candidate skills")

    for tier in ("cheap", "mid"):
        if not candidates:
            break
        model = config.MODELS[tier]
        with trace.timed() as t:
            res, obj, err = gate.fill(model, question, candidates)
        out["cost"] += res.cost_usd
        trace.step(f"{tier} model · pick skill + fill params", tier, ms=t["ms"], cost=res.cost_usd, model=res.model,
                   ok=obj is not None and bool(obj.get("skillId")),
                   detail=(obj or {}).get("skillId") and f"picked {obj.get('skillId')}" or err or "no skill fits")
        rows = None
        chosen = None
        if obj is not None:
            sid = obj.get("skillId")
            if not sid:
                out["trace"].append(f"{tier}: no skill fits")
                ledger.log_run(adb, mode="downshift", path=tier, family=family, model=res.model, cost=res.cost_usd,
                               tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms,
                               case_id=case_id, batch_id=batch_id, extra={"outcome": "no_skill"})
                break  # nothing fits: go learn
            chosen = next((s for s in candidates if s["skillId"] == sid), None)
            if chosen is None:
                err = f"unknown skill {sid!r}"
            else:
                try:
                    pipeline, typed = skills.render(chosen, obj.get("params") or {})
                    trace.step("validate params", "check", detail=", ".join(f"{k}={_show(v)}" for k, v in typed.items() if v is not None))
                    rows, db_ms = nl2mql.run_pipeline(data, pipeline)
                    trace.step("aggregate on Atlas", "db", ms=db_ms,
                               detail=" → ".join(next(iter(st)) for st in pipeline))
                    out["params"] = {k: _show(v) for k, v in typed.items() if v is not None}
                    if not rows:
                        err, rows = "empty result", None
                except Exception as e:  # noqa: BLE001
                    err = f"{type(e).__name__}: {e}"
                    trace.step("validate params", "check", ok=False, detail=err)
        ok = rows is not None
        ledger.log_run(adb, mode="downshift", path=tier, family=family, model=res.model, cost=res.cost_usd,
                       tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms,
                       case_id=case_id, batch_id=batch_id,
                       skill=f"{chosen['skillId']}@v{chosen['version']}" if chosen else None,
                       extra={"outcome": "ok" if ok else "fail", "error": err})
        if ok:
            out.update(rows=rows, path=tier, skill=f"{chosen['skillId']}@v{chosen['version']}")
            out["trace"].append(f"{tier}: answered with {out['skill']}")
            return out
        out["trace"].append(f"{tier}: failed ({err})")
        if tier == "mid":
            ledger.event(adb, "escalated", question=question, reason=err)

    # learn path. While skills are flagged for repair, the frontier answers but does not learn a duplicate skill.
    repairing = adb.skills.count_documents({"status": "flagged"}) > 0
    r = learn.learn(adb, data, question, schema_text, batch_id=batch_id, family=family, make_skill=not repairing)
    out["cost"] += r["cost"]
    out["rows"] = r["rows"]
    out["path"] = "frontier" if repairing else "learn"
    out["trace"] += [f"learn: {s}" for s in r["steps"]] + ([f"learn error: {r['error']}"] if r["error"] else [])
    if r["skill"]:
        out["skill"] = f"{r['skill']['skillId']}@v{r['skill']['version']} ({r['skill']['status']})"
    return out
