"""Stage: load the dataset file into MongoDB collection `raw_posts`.

Each document:  {_id: <stable post id>, source_row: <row number>, data: {<original columns>}, ingested_at}
Re-running is safe: documents whose _id already exists are skipped (counted, never duplicated).
"""
import hashlib
import json
import logging
from datetime import datetime, timezone

from pymongo.errors import BulkWriteError

from src.database import RAW_POSTS
from src.dataset_io import DatasetFormatError, iter_records, read_header

log = logging.getLogger(__name__)


def is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return str(value).strip().lower() in ("", "nan", "none", "null")


def make_post_id(row: dict, id_column: str) -> str:
    """Use the dataset's own id column when present, else a hash of the whole row."""
    if id_column and not is_blank(row.get(id_column)):
        return str(row[id_column]).strip()
    canonical = json.dumps(row, sort_keys=True, default=str, ensure_ascii=False)
    return "h_" + hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:24]


def check_required_columns(columns: list, settings) -> None:
    missing = []
    if settings.col_date not in columns:
        missing.append(f"date column '{settings.col_date}' (COL_DATE)")
    has_text = settings.col_text and settings.col_text in columns
    has_tags = settings.col_hashtags and settings.col_hashtags in columns
    if not (has_text or has_tags):
        missing.append(f"text column '{settings.col_text}' (COL_TEXT) or hashtag column '{settings.col_hashtags}' (COL_HASHTAGS)")
    if settings.col_id and settings.col_id not in columns:
        missing.append(f"id column '{settings.col_id}' (COL_ID)")
    if missing:
        raise DatasetFormatError(
            "These configured columns are not in the file: " + "; ".join(missing)
            + f". Columns found in the file: {columns}. Fix the COL_* values in your .env file."
        )


def ingest_dataset(db, path: str, settings) -> dict:
    columns = read_header(path)
    check_required_columns(columns, settings)

    counters = {"bad_lines": 0}
    summary = {"file": str(path), "processed": 0, "inserted": 0, "skipped_duplicates": 0,
               "rejected_blank": 0, "rejected_malformed_lines": 0}
    row_number = 0
    for records in iter_records(path, settings.batch_size, counters):
        documents = []
        for row in records:
            row_number += 1
            summary["processed"] += 1
            key_fields = [row.get(settings.col_date), row.get(settings.col_text) if settings.col_text else None,
                          row.get(settings.col_hashtags) if settings.col_hashtags else None]
            if all(is_blank(value) for value in key_fields):
                summary["rejected_blank"] += 1
                continue
            documents.append({"_id": make_post_id(row, settings.col_id), "source_row": row_number,
                              "data": row, "ingested_at": datetime.now(timezone.utc)})
        if not documents:
            continue
        try:
            result = db[RAW_POSTS].insert_many(documents, ordered=False)
            summary["inserted"] += len(result.inserted_ids)
        except BulkWriteError as error:
            errors = error.details.get("writeErrors", [])
            duplicates = [e for e in errors if e.get("code") == 11000]
            others = [e for e in errors if e.get("code") != 11000]
            if others:  # real problem - do not hide it
                raise RuntimeError(f"MongoDB rejected documents: {others[0].get('errmsg')}") from error
            summary["skipped_duplicates"] += len(duplicates)
            summary["inserted"] += error.details.get("nInserted", 0)
        log.info("Ingested %s rows so far", summary["processed"])
    summary["rejected_malformed_lines"] = counters["bad_lines"]
    summary["columns"] = columns
    summary["raw_posts_in_db"] = db[RAW_POSTS].count_documents({})
    return summary
