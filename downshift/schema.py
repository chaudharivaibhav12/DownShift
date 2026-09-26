"""Infer a compact schema for the queried collection and keep it in `schema_registry`."""
from collections import Counter, defaultdict
from datetime import datetime, timezone

from bson import Decimal128, ObjectId


def _type_name(v) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "double"
    if isinstance(v, Decimal128):
        return "decimal"
    if isinstance(v, str):
        return "string"
    if isinstance(v, datetime):
        return "date"
    if isinstance(v, ObjectId):
        return "objectId"
    if isinstance(v, dict):
        return "object"
    if isinstance(v, list):
        return "array"
    if v is None:
        return "null"
    return type(v).__name__


def _walk(doc, prefix, types, strings):
    for k, v in doc.items():
        path = f"{prefix}{k}"
        if isinstance(v, list):
            types[path][ "array"] += 1
            for item in v[:20]:
                if isinstance(item, dict):
                    _walk(item, f"{path}.", types, strings)
                else:
                    types[f"{path}[]"][_type_name(item)] += 1
                    if isinstance(item, str):
                        strings[f"{path}[]"][item] += 1
        elif isinstance(v, dict):
            types[path]["object"] += 1
            _walk(v, f"{path}.", types, strings)
        else:
            types[path][_type_name(v)] += 1
            if isinstance(v, str):
                strings[path][v] += 1


def infer_schema(coll, sample_size: int = 500, max_enum: int = 15) -> list[dict]:
    """Return [{path, types, examples?}]; low-cardinality string fields list their values."""
    types: dict[str, Counter] = defaultdict(Counter)
    strings: dict[str, Counter] = defaultdict(Counter)
    try:
        docs = list(coll.aggregate([{"$sample": {"size": sample_size}}]))
    except Exception:
        docs = list(coll.find().limit(sample_size))
    for d in docs:
        _walk(d, "", types, strings)
    fields = []
    for path in sorted(types):
        if path == "_id":
            continue
        entry = {"path": path, "types": sorted(types[path])}
        vals = strings.get(path)
        if vals and len(vals) <= max_enum:
            entry["values"] = sorted(vals)
        fields.append(entry)
    return fields


def schema_for_prompt(fields: list[dict]) -> str:
    lines = []
    for f in fields:
        line = f"- {f['path']}: {'/'.join(f['types'])}"
        if f.get("values"):
            line += f"  (values: {', '.join(f['values'])})"
        lines.append(line)
    return "\n".join(lines)


def snapshot(registry_coll, data_coll, collection_name: str) -> dict:
    """Store a new schema version; record which field paths changed since the last one."""
    fields = infer_schema(data_coll)
    prev = registry_coll.find_one({"collection": collection_name}, sort=[("version", -1)])
    prev_paths = {f["path"] for f in prev["fields"]} if prev else set()
    new_paths = {f["path"] for f in fields}
    if prev and prev_paths == new_paths:
        return {**prev, "changedFields": []}  # nothing changed: don't mint a new version
    doc = {
        "collection": collection_name,
        "version": (prev["version"] + 1) if prev else 1,
        "fields": fields,
        "changedFields": sorted(prev_paths ^ new_paths) if prev else [],
        "at": datetime.now(timezone.utc),
    }
    registry_coll.insert_one(doc)
    return doc


def latest(registry_coll, collection_name: str) -> dict | None:
    return registry_coll.find_one({"collection": collection_name}, sort=[("version", -1)])
