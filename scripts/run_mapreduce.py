"""Run the genuine MongoDB MapReduce jobs and validate their output."""
import argparse
import sys

import _bootstrap  # noqa: F401

from config import VALID_GRANULARITIES, load_settings
from src.database import TOPIC_MENTIONS, check_connection, get_client
from src.mapreduce_jobs import MapReduceError, run_all_jobs


def main() -> int:
    _bootstrap.setup_logging("mapreduce")
    settings = load_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--granularity", choices=VALID_GRANULARITIES, default=settings.granularity)
    args = ap.parse_args()
    client = get_client(settings)
    ok, version = check_connection(client)
    if not ok:
        print(f"Cannot connect to MongoDB: {version}")
        return 1
    db = client[settings.db_name]
    if db[TOPIC_MENTIONS].estimated_document_count() == 0:
        print("topic_mentions is empty. Run ingest_data.py and preprocess_data.py first.")
        return 1
    try:
        status = run_all_jobs(db, args.granularity, version)
    except MapReduceError as error:
        print(f"MAPREDUCE FAILED: {error}")
        return 1
    print(f"\n=== MAPREDUCE STATUS: {status['status']} (server {version}, granularity={args.granularity}) ===")
    for name, stats in status["jobs"].items():
        print(f"{name}: {stats}")
    print("Independent validation:", status["validation"])
    if status["status"] != "success":
        return 1
    print("Next: python scripts/detect_comebacks.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
