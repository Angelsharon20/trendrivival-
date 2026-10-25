"""Clean raw_posts into clean_posts and extract topic_mentions. Prints the cleaning summary."""
import sys

import _bootstrap  # noqa: F401
from pymongo.errors import PyMongoError

from config import load_settings
from src.database import RAW_POSTS, check_connection, get_client, save_metadata
from src.preprocessing import preprocess_posts


def main() -> int:
    _bootstrap.setup_logging("preprocessing")
    settings = load_settings()
    client = get_client(settings)
    ok, info = check_connection(client)
    if not ok:
        print(f"Cannot connect to MongoDB: {info}")
        return 1
    db = client[settings.db_name]
    if db[RAW_POSTS].estimated_document_count() == 0:
        print("raw_posts is empty. Run: python scripts/ingest_data.py")
        return 1
    try:
        summary = preprocess_posts(db, settings)
    except PyMongoError as error:
        print(f"PREPROCESSING FAILED: {error}")
        return 1
    save_metadata(db, "preprocessing_summary", summary)
    print("\n=== CLEANING SUMMARY ===")
    for key in ("original_count", "duplicates", "missing_timestamp", "missing_text", "missing_hashtags",
                "retained", "rejected_total", "final_usable_count", "topic_mode_used", "topic_mentions",
                "distinct_topics_in_mentions", "date_start", "date_end", "timezone"):
        print(f"{key:28}: {summary[key]}")
    print("Rejected by reason:", summary["rejected"])
    print("Next: python scripts/run_mapreduce.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
