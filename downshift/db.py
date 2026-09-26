"""MongoDB access: one client, the queried data collection, and Downshift's own collections."""
from functools import lru_cache

from pymongo import MongoClient

from . import config


@lru_cache(maxsize=1)
def client() -> MongoClient:
    return MongoClient(config._req("MONGODB_URI"), appname="downshift")


def data_coll(c: MongoClient | None = None):
    return (c or client())[config.DATA_DB][config.DATA_COLLECTION]


def app_db(c: MongoClient | None = None):
    return (c or client())[config.APP_DB]
