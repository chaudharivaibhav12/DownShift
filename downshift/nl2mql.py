"""Natural language -> aggregation pipeline, with safety checks and a guarded run.

Used for the baselines now; later the learn path reuses it for the frontier model's first answer.
"""
import time

from bson import json_util

from . import config, llm

SYSTEM = """You write MongoDB aggregation pipelines for the `{collection}` collection.

Schema (field path: type, plus known values for small string fields):
{schema}

Notes:
- `items` is an array of line items; each has name, tags (array of strings), price (decimal) and quantity (int).
- Revenue means the sum of items.price * items.quantity.
- Dates are UTC. Use MongoDB Extended JSON for date literals: {{"$date": "2016-03-01T00:00:00Z"}}.
- Use only read stages ($match, $unwind, $group, $project, $addFields, $sort, $limit, $count, $facet, $bucket, $set, $unset).

Reply with ONLY a JSON object, no prose: {{"pipeline": [ ...stages... ]}}"""

FORBIDDEN = {"$out", "$merge", "$function", "$accumulator", "$where", "$lookup", "$unionWith",
             "$graphLookup", "$currentOp", "$listSessions", "$collStats", "$indexStats", "$planCacheStats"}


class UnsafePipeline(ValueError):
    pass


def _walk_keys(v):
    if isinstance(v, dict):
        for k, x in v.items():
            yield k
            yield from _walk_keys(x)
    elif isinstance(v, list):
        for x in v:
            yield from _walk_keys(x)


def parse_pipeline(text: str) -> list[dict]:
    raw = llm.extract_json_text(text)
    obj = json_util.loads(raw)  # turns {"$date": ...} into datetime
    pipeline = obj.get("pipeline") if isinstance(obj, dict) else obj
    if not isinstance(pipeline, list) or not all(isinstance(s, dict) and len(s) == 1 for s in pipeline):
        raise ValueError("pipeline must be a list of single-key stage objects")
    return pipeline


def check_safe(pipeline: list[dict]) -> None:
    bad = FORBIDDEN.intersection(_walk_keys(pipeline))
    if bad:
        raise UnsafePipeline(f"forbidden operators: {sorted(bad)}")


def run_pipeline(coll, pipeline: list[dict]) -> tuple[list[dict], int]:
    check_safe(pipeline)
    t0 = time.perf_counter()
    rows = list(coll.aggregate(pipeline + [{"$limit": config.MAX_RESULT_ROWS}], maxTimeMS=config.MAX_TIME_MS))
    return rows, int((time.perf_counter() - t0) * 1000)


def generate(model: str, question: str, schema_text: str) -> tuple[llm.LLMResult, list[dict] | None, str | None]:
    """Ask `model` for a pipeline. Returns (llm result, pipeline or None, error or None)."""
    system = SYSTEM.format(collection=config.DATA_COLLECTION, schema=schema_text)
    res = llm.chat(model, system, question)
    if res.error:
        return res, None, f"llm: {res.error}"
    try:
        return res, parse_pipeline(res.text), None
    except Exception as e:  # noqa: BLE001 - model output can be anything
        return res, None, f"parse: {e}"
