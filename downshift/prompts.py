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
  including whether date bounds are inclusive or exclusive, with one example
  (e.g. "exclusive end: the day after the period, March 2015 -> 2015-04-01").
- For a string param with a known small set of values in the schema, list them in "values".
- A filter the question might leave out (e.g. "for all stores") is an optional param: "optional": true. When an
  optional param is not given, the key that holds its placeholder is removed, so put it as its own key in $match.
- Anticipate the family: if similar questions would often filter on a field this question did not (e.g. one store
  location, one purchase method), add it as an optional param in its own $match key even though originalParams
  leaves it out.
- skillId: short snake_case name of the question family. intent: one sentence describing questions it answers.
- originalParams: the param values that reproduce the working pipeline exactly.
- testQuestions: 12 new, varied natural-language questions of the same family with the params each needs.
  Use values that exist in the schema and dates inside the range the data covers. Vary wording a lot, but every test question must state every required
  param explicitly: a concrete number for counts/limits, a concrete month, quarter, half or year for dates.
  No vague periods ("summer", "recently") and no questions without a number when the skill needs one.
  At least 3 test questions must use each optional param and at least 2 must leave it out.

Reply with ONLY this JSON:
{{"skillId": "...", "intent": "...", "params": {{"name": {{"type": "...", "description": "...", "optional": false}}}},
  "template": [ ...stages... ], "originalParams": {{...}},
  "testQuestions": [{{"question": "...", "params": {{...}}}}]}}"""


SELECT_AND_FILL = """TASK: SELECT_AND_FILL
You route a data question to one of these saved skills and fill in its parameters. Today is {today}.

Skills:
{skills}

Rules:
- First write in "asksFor" what the question asks for: the measure and the grouping (e.g. "revenue per store",
  "coupon rate per purchase method", "units sold per item"). Pick a skill only if its intent computes exactly that
  measure. Sharing a store name, a year or the word "sales" is not enough. If none fits, use "skillId": null.
- Every filter the question states (a store, a tag, a purchase method, ...) must go into one of the skill's params.
  If the skill has no param for a stated filter, the skill does not fit: use "skillId": null. Never drop a filter.
- Fill every required param from the question. Numbers are plain integers (5, not "5").
- Dates are ISO "YYYY-MM-DD". A start is the first day of the period. An exclusive end is the first day AFTER the
  period: "in 2016" -> 2016-01-01 to 2017-01-01; "March 2015" -> 2015-03-01 to 2015-04-01;
  "Q1 2016" -> 2016-01-01 to 2016-04-01; "first half of 2017" -> 2017-01-01 to 2017-07-01;
  "December 2015" -> 2015-12-01 to 2016-01-01.
- Leave an optional param out when the question does not restrict it.

Reply with ONLY JSON: {{"asksFor": "...", "skillId": "...", "params": {{...}}}}"""


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
