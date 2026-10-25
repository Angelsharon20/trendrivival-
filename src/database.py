"""MongoDB connection helpers, collection names, indexes and pipeline metadata."""
from datetime import datetime, timezone

from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError

RAW_POSTS = "raw_posts"
CLEAN_POSTS = "clean_posts"
TOPIC_MENTIONS = "topic_mentions"
TOPIC_PERIOD_COUNTS = "topic_period_counts"   # output of MapReduce Job 1
TOPIC_SUMMARY = "topic_summary"               # output of MapReduce Job 2
COMEBACK_RESULTS = "comeback_results"
PIPELINE_METADATA = "pipeline_metadata"       # run summaries (ingestion, cleaning, MapReduce status ...)


def get_client(settings, timeout_ms: int = 5000) -> MongoClient:
    return MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=timeout_ms)


def get_db(settings, client: MongoClient = None):
    client = client or get_client(settings)
    return client[settings.db_name]


def check_connection(client: MongoClient):
    """Return (True, server_version) or (False, error_message). Never hides the error."""
    try:
        info = client.server_info()
        return True, info.get("version", "unknown")
    except PyMongoError as error:
        return False, f"{type(error).__name__}: {error}"


def ensure_indexes(db) -> None:
    db[CLEAN_POSTS].create_index([("created_at", ASCENDING)])
    db[TOPIC_MENTIONS].create_index([("topic", ASCENDING), ("created_at", ASCENDING)])
    db[TOPIC_MENTIONS].create_index([("post_id", ASCENDING)])
    db[COMEBACK_RESULTS].create_index([("topic", ASCENDING)])
    db[COMEBACK_RESULTS].create_index([("status", ASCENDING)])


def save_metadata(db, key: str, document: dict) -> None:
    document = dict(document)
    document["_id"] = key
    document["saved_at"] = datetime.now(timezone.utc)
    db[PIPELINE_METADATA].replace_one({"_id": key}, document, upsert=True)


def get_metadata(db, key: str):
    return db[PIPELINE_METADATA].find_one({"_id": key})
