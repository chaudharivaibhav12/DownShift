"""Prompts used by the skill engine. Each starts with a TAG line so logs (and the offline stub) can tell them apart."""

GENERALIZE = """TASK: GENERALIZE
You turn a working MongoDB aggregation pipeline that answered one question into a reusable skill.

Collection: {collection}
Schema:
{schema}

Question: {question}
Working pipeline (Extended JSON):
{pipeline}

Make a template of the same pipeline where every value that came from the question (dates, numbers, names,
tags, limits) becomes a placeholder string "{{{{name}}}}" used as a whole JSON value. Keep everything else identical.
A date placeholder is the bare string "{{{{start}}}}" (it is converted to a real date), never {{"$date": "{{{{start}}}}"}}.
Rules:
- Param types: "date" (ISO 8601 date, e.g. "2017-08-01"), "int", or "string". Give each a short description,
  including whether date bounds are inclusive or exclusive.
- For a string param with a known small set of values in the schema, list them in "values".
- A filter the question might leave out (e.g. "for all stores") is an optional param: "optional": true. When an
  optional param is not given, the key that holds its placeholder is removed, so put it as its own key in $match.
- skillId: short snake_case name of the question family. intent: one sentence describing questions it answers.
- originalParams: the param values that reproduce the working pipeline exactly.
- testQuestions: 8 new, varied natural-language questions of the same family with the params each needs.
  Use values that exist in the schema. Vary wording a lot.

Reply with ONLY this JSON:
{{"skillId": "...", "intent": "...", "params": {{"name": {{"type": "...", "description": "...", "optional": false}}}},
  "template": [ ...stages... ], "originalParams": {{...}},
  "testQuestions": [{{"question": "...", "params": {{...}}}}]}}"""


SELECT_AND_FILL = """TASK: SELECT_AND_FILL
You route a data question to one of these saved skills and fill in its parameters. Today is {today}.

Skills:
{skills}

Rules:
- Pick the skill whose intent matches the question. If none fits exactly, answer {{"skillId": null}}.
- Fill every required param. Dates are ISO "YYYY-MM-DD"; follow each param's description for inclusive/exclusive
  bounds (e.g. "in 2016" with an exclusive end means start 2016-01-01, end 2017-01-01).
- Leave an optional param out when the question does not restrict it.

Reply with ONLY JSON: {{"skillId": "...", "params": {{...}}}}"""


def skills_block(skills: list[dict]) -> str:
    out = []
    for s in skills:
        params = "; ".join(
            f"{k} ({v.get('type')}{', optional' if v.get('optional') else ''}"
            f"{', one of ' + '/'.join(map(str, v['values'])) if v.get('values') else ''}): {v.get('description', '')}"
            for k, v in s["params"].items())
        ex = " | ".join(s.get("examples", [])[:3])
        out.append(f"- skillId: {s['skillId']}\n  intent: {s['intent']}\n  params: {params}\n  examples: {ex}")
    return "\n".join(out)


REPAIR = """TASK: REPAIR
A saved MongoDB aggregation skill broke because the `{collection}` collection's schema changed.

Fields that changed (appeared or disappeared): {changed}

Current schema:
{schema}

Skill intent: {intent}
Params (keep exactly these names and types): {params}
Old template (Extended JSON, "{{{{name}}}}" strings are placeholders):
{template}

Write date placeholders as bare strings like "{{{{start}}}}", never inside {{"$date": ...}}.
Rewrite the template so it answers the same questions on the new schema. Keep every placeholder and the
output shape (same group keys and output field names) unless the change forces otherwise.

Reply with ONLY JSON: {{"template": [ ...stages... ], "note": "one sentence on what you changed"}}"""


REFLECT = """TASK: REFLECT
A saved skill failed its promotion gate: the cheap model could not fill its parameters reliably.
The pipeline template is correct (it passed a self-check). Only the cheap-facing description is at fault.

Skill: {skillId}
Intent: {intent}
Params (JSON): {params}
Examples: {examples}

Gate traces the cheap model got RIGHT (question -> params it filled):
{passes}

Gate traces the cheap model got WRONG (question, error, its raw output):
{failures}

Contrast the winning and losing traces. Find what the losing questions have in common that the descriptions
do not cover (a phrasing, an inclusive/exclusive bound, an omitted param, a value spelling), then rewrite the
intent, the param descriptions and the examples so a small model fills the params correctly.
Rules: keep every param name, type, optional flag and values list exactly as given. Change descriptions only.

Reply with ONLY JSON: {{"intent": "...", "params": {{"name": {{"description": "..."}}}}, "examples": ["..."],
  "note": "one sentence: the failure pattern and what you changed"}}"""
