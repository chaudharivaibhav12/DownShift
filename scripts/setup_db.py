"""Step 1 setup: create Downshift's collections and indexes, snapshot the data schema. Safe to re-run.

Run:  python -m scripts.setup_db
"""
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid

from downshift import config, db, schema


def ensure_collections(adb):
    existing = set(adb.list_collection_names())

    if "ledger" not in existing:
        try:
            adb.create_collection(
                "ledger",
                timeseries={"timeField": "ts", "metaField": "meta", "granularity": "seconds"},
            )
            print("created ledger (time-series)")
        except (CollectionInvalid, Exception) as e:  # time-series unsupported (e.g. local mock)
            adb.create_collection("ledger") if "ledger" not in adb.list_collection_names() else None
            print(f"created ledger as a normal collection ({type(e).__name__})")

    for name in ("skills", "test_cases", "schema_registry", "events", "runs", "repairs", "answers"):
        if name not in existing:
            adb.create_collection(name)
            print(f"created {name}")

    adb.skills.create_index([("skillId", ASCENDING), ("version", ASCENDING)], unique=True)
    adb.skills.create_index([("fieldsUsed", ASCENDING)])
    adb.skills.create_index([("status", ASCENDING)])
    adb.test_cases.create_index([("family", ASCENDING), ("split", ASCENDING)])
    adb.test_cases.create_index([("caseId", ASCENDING)], unique=True)
    adb.schema_registry.create_index([("collection", ASCENDING), ("version", DESCENDING)], unique=True)
    adb.events.create_index([("ts", ASCENDING)], expireAfterSeconds=86_400)
    adb.runs.create_index([("batchId", ASCENDING), ("mode", ASCENDING)])
    print("indexes ok")


def main():
    c = db.client()
    adb = db.app_db(c)
    ensure_collections(adb)

    data = db.data_coll(c)
    if data.estimated_document_count() == 0:
        raise SystemExit(f"{config.DATA_DB}.{config.DATA_COLLECTION} is empty: load the Atlas sample dataset first.")

    snap = schema.snapshot(adb.schema_registry, data, config.DATA_COLLECTION)
    print(f"schema_registry: {config.DATA_COLLECTION} v{snap['version']} with {len(snap['fields'])} fields")
    print(schema.schema_for_prompt(snap["fields"]))


if __name__ == "__main__":
    main()
