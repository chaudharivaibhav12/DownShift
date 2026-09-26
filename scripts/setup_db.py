"""Step 1 setup: create Downshift's collections and indexes, snapshot the data schema. Safe to re-run.

Run:  python -m scripts.setup_db
"""
from downshift import config, db, schema
from downshift.db import ensure_collections  # noqa: F401  (kept importable from here)


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
