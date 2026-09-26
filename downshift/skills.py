"""Skills: versioned, parameterized aggregation pipelines.

A skill document (collection `skills`):
{
  skillId, version, status: candidate | promoted | retired | rejected,
  intent, examples: [question, ...],
  params: {name: {type: date|int|string, description, optional?, values?, min?, max?}},
  templateJson: Extended-JSON string of the pipeline with "{{name}}" placeholders,
  fieldsUsed: [field.path, ...],
  createdBy: model id, parentVersion, gateReport, createdAt
}
The template is stored as a string because pipelines are full of `$`-prefixed keys.
"""
import re
from datetime import datetime, timezone

from bson import json_util

from . import nl2mql

PLACEHOLDER = re.compile(r"^\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}$")
_DROP = object()  # marker: an optional param was not given, so drop the key that used it


class ParamError(ValueError):
    pass


# ------------------------------------------------------------------ params

def _parse_date(v) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, dict) and "$date" in v:
        v = v["$date"]
    if not isinstance(v, str):
        raise ParamError(f"not a date: {v!r}")
    s = v.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError as e:
        raise ParamError(f"bad date {v!r}") from e
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def validate_params(spec: dict, given: dict) -> dict:
    """Check and convert model-filled params against the skill's spec. Returns typed values."""
    given = given or {}
    unknown = set(given) - set(spec)
    if unknown:
        raise ParamError(f"unknown params {sorted(unknown)}")
    out = {}
    for name, s in spec.items():
        v = given.get(name)
        if v is None or v == "":
            if s.get("optional"):
                out[name] = None
                continue
            if "default" in s:
                v = s["default"]
            else:
                raise ParamError(f"missing param {name}")
        t = s.get("type", "string")
        if t == "date":
            v = _parse_date(v)
        elif t == "int":
            try:
                v = int(v)
            except (TypeError, ValueError) as e:
                raise ParamError(f"{name} must be an int") from e
            if "min" in s and v < s["min"] or "max" in s and v > s["max"]:
                raise ParamError(f"{name}={v} out of range")
        else:
            v = str(v)
        if s.get("values") and v not in s["values"]:
            raise ParamError(f"{name}={v!r} not one of {s['values']}")
        out[name] = v
    return out


# ------------------------------------------------------------------ templates

def substitute(template, values: dict):
    """Replace "{{name}}" strings with typed values. A None optional value drops its enclosing key."""
    if isinstance(template, str):
        m = PLACEHOLDER.match(template)
        if not m:
            return template
        name = m.group(1)
        if name not in values:
            raise ParamError(f"template uses unknown param {name}")
        return _DROP if values[name] is None else values[name]
    if isinstance(template, list):
        return [x for x in (substitute(t, values) for t in template) if x is not _DROP]
    if isinstance(template, dict):
        out = {}
        for k, v in template.items():
            sv = substitute(v, values)
            if sv is not _DROP:
                out[k] = sv
        return out
    return template


def placeholders(template) -> set[str]:
    found = set()
    if isinstance(template, str):
        m = PLACEHOLDER.match(template)
        if m:
            found.add(m.group(1))
    elif isinstance(template, list):
        for t in template:
            found |= placeholders(t)
    elif isinstance(template, dict):
        for v in template.values():
            found |= placeholders(v)
    return found


def fields_used(pipeline) -> list[str]:
    """Field paths a pipeline reads: "$a.b" references and plain keys inside $match."""
    fields = set()

    def walk(v, in_match=False):
        if isinstance(v, dict):
            for k, x in v.items():
                if in_match and not k.startswith("$"):
                    fields.add(k)
                walk(x, in_match or k == "$match")
        elif isinstance(v, list):
            for x in v:
                walk(x, in_match)
        elif isinstance(v, str) and v.startswith("$") and not v.startswith("$$") and len(v) > 1:
            if not PLACEHOLDER.match(v):
                fields.add(v[1:])

    for stage in pipeline:
        walk(stage)
    return sorted(fields)


def load_template(skill: dict) -> list:
    return json_util.loads(skill["templateJson"])


def render(skill: dict, raw_params: dict) -> tuple[list, dict]:
    """Validate params and return (runnable pipeline, typed params)."""
    typed = validate_params(skill["params"], raw_params)
    pipeline = substitute(load_template(skill), typed)
    nl2mql.check_safe(pipeline)
    return pipeline, typed


# ------------------------------------------------------------------ store

def new_skill(skills_coll, skill_id: str, **fields) -> dict:
    last = skills_coll.find_one({"skillId": skill_id}, sort=[("version", -1)])
    doc = {
        "skillId": skill_id,
        "version": (last["version"] + 1) if last else 1,
        "status": "candidate",
        "parentVersion": last["version"] if last else None,
        "createdAt": datetime.now(timezone.utc),
        **fields,
    }
    skills_coll.insert_one(doc)
    return doc


def promote(skills_coll, skill: dict, report: dict) -> None:
    skills_coll.update_many({"skillId": skill["skillId"], "status": "promoted"}, {"$set": {"status": "retired"}})
    skills_coll.update_one({"_id": skill["_id"]}, {"$set": {"status": "promoted", "gateReport": report}})
    skill.update(status="promoted", gateReport=report)


def reject(skills_coll, skill: dict, report: dict) -> None:
    skills_coll.update_one({"_id": skill["_id"]}, {"$set": {"status": "rejected", "gateReport": report}})
    skill.update(status="rejected", gateReport=report)


def promoted(skills_coll) -> list[dict]:
    return list(skills_coll.find({"status": "promoted"}))


def card(skill: dict) -> str:
    """Human-readable one-screen summary."""
    g = skill.get("gateReport") or {}
    lines = [
        f"{skill['skillId']} v{skill['version']} [{skill['status']}]  gate {g.get('passed', '-')}/{g.get('total', '-')}",
        f"  intent: {skill['intent']}",
        f"  params: " + ", ".join(f"{k}:{v.get('type')}{'?' if v.get('optional') else ''}"
                                   for k, v in skill["params"].items()),
        f"  reads:  {', '.join(skill.get('fieldsUsed', []))}",
    ]
    return "\n".join(lines)
