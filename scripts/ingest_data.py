"""Import the dataset file into MongoDB (collection raw_posts). Safe to re-run."""
import argparse
import sys

import _bootstrap  # noqa: F401
from pymongo.errors import PyMongoError

from config import load_settings
from src.database import check_connection, get_client, save_metadata
from src.dataset_io import DatasetFormatError
from src.ingestion import ingest_dataset


def main() -> int:
    _bootstrap.setup_logging("ingestion")
    settings = load_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=settings.dataset_path)
    args = ap.parse_args()
    if not args.path:
        print("No dataset path. Set DATASET_PATH in .env or pass --path. See data/README.md.")
        return 1
    client = get_client(settings)
    ok, info = check_connection(client)
    if not ok:
        print(f"Cannot connect to MongoDB: {info}")
        return 1
    db = client[settings.db_name]
    try:
        summary = ingest_dataset(db, args.path, settings)
    except (DatasetFormatError, RuntimeError, PyMongoError) as error:
        print(f"INGESTION FAILED: {error}")
        return 1
    summary.update({"dataset_name": settings.dataset_name, "dataset_source": settings.dataset_source,
                    "dataset_license": settings.dataset_license})
    save_metadata(db, "ingestion_summary", summary)
    print("\n=== INGESTION SUMMARY ===")
    for key in ("processed", "inserted", "skipped_duplicates", "rejected_blank", "rejected_malformed_lines", "raw_posts_in_db"):
        print(f"{key:28}: {summary[key]}")
    print("Next: python scripts/preprocess_data.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
