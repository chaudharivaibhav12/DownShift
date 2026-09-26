"""MongoDB access: one client, the queried data collection, and Downshift's own collections."""
from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import CollectionInvalid

from . import config


@lru_cache(maxsize=1)
def client() -> MongoClient:
    return MongoClient(config._req("MONGODB_URI"), appname="downshift")


def data_coll(c: MongoClient | None = None):
    return (c or client())[config.DATA_DB][config.DATA_COLLECTION]


def app_db(c: MongoClient | None = None):
    return (c or client())[config.APP_DB]


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
