"""Check a dataset BEFORE importing it. Prints a validation report; exit code 1 if it is unsuitable.

Example:
  python scripts/validate_dataset.py --path data/my_posts.csv --col-text text --col-date created_at --col-hashtags hashtags
Settings default to the values in your .env file.
"""
import argparse
import sys
from collections import Counter

import _bootstrap  # noqa: F401

from config import load_settings
from src.dataset_io import DatasetFormatError, iter_records, read_header
from src.ingestion import is_blank
from src.periods import period_start
from src.preprocessing import content_hash, normalise_text, normalise_timestamp
from src.topic_extraction import extract_topics


def main() -> int:
    s = load_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default=s.dataset_path)
    ap.add_argument("--col-text", default=s.col_text)
    ap.add_argument("--col-date", default=s.col_date)
    ap.add_argument("--col-hashtags", default=s.col_hashtags)
    ap.add_argument("--min-records", type=int, default=50000)
    ap.add_argument("--min-span-days", type=int, default=365)
    ap.add_argument("--min-active-weeks", type=int, default=52)
    a = ap.parse_args()
    if not a.path:
        print("No dataset path. Pass --path or set DATASET_PATH in .env (see data/README.md).")
        return 1

    try:
        columns = read_header(a.path)
    except DatasetFormatError as error:
        print(f"ERROR: {error}")
        return 1
    print(f"File: {a.path}\nColumns found ({len(columns)}): {columns}")
    for label, col in (("date", a.col_date), ("text", a.col_text), ("hashtags", a.col_hashtags)):
        if col and col not in columns:
            print(f"  WARNING: {label} column '{col}' is not in the file")
    if a.col_date not in columns or not ((a.col_text in columns) or (a.col_hashtags in columns)):
        print("FAIL: a date column and a text or hashtag column are required.")
        return 1

    total = usable = bad_ts = empty_text = missing_date = missing_text = missing_tags = duplicates = 0
    with_hashtags = 0
    seen, weeks, first, last = set(), Counter(), None, None
    counters = {}
    for records in iter_records(a.path, 5000, counters):
        for row in records:
            total += 1
            missing_date += is_blank(row.get(a.col_date))
            text = normalise_text(row.get(a.col_text)) if a.col_text in columns else ""
            tags = row.get(a.col_hashtags) if a.col_hashtags and a.col_hashtags in columns else None
            missing_text += not text
            missing_tags += is_blank(tags) if a.col_hashtags else 0
            stamp = normalise_timestamp(row.get(a.col_date))
            if stamp is None:
                bad_ts += 1
                continue
            if not text and is_blank(tags):
                empty_text += 1
                continue
            topics = extract_topics(text, tags, "hashtag")
            with_hashtags += bool(topics)
            digest = content_hash(text, stamp, topics)
            if digest in seen:
                duplicates += 1
                continue
            seen.add(digest)
            usable += 1
            weeks[period_start(stamp, "week")] += 1
            first = stamp if first is None or stamp < first else first
            last = stamp if last is None or stamp > last else last

    span = (last - first).days if first else 0
    print("\n=== DATASET VALIDATION REPORT ===")
    print(f"Original records        : {total}")
    print(f"Malformed lines skipped : {counters.get('bad_lines', 0)}")
    print(f"Missing date            : {missing_date}")
    print(f"Invalid/missing timestamp: {bad_ts}")
    print(f"Missing text            : {missing_text}")
    print(f"Missing hashtags        : {missing_tags}")
    print(f"Empty (no text & tags)  : {empty_text}")
    print(f"Duplicate records       : {duplicates}")
    print(f"Usable records          : {usable}")
    print(f"Date range (UTC)        : {first} -> {last}  ({span} days)")
    print(f"Active weeks            : {len(weeks)}")
    print(f"Records with hashtags   : {with_hashtags} ({(with_hashtags / usable * 100 if usable else 0):.1f}% of usable)")
    checks = [(f"usable records >= {a.min_records}", usable >= a.min_records),
              (f"date span >= {a.min_span_days} days", span >= a.min_span_days),
              (f"active weeks >= {a.min_active_weeks}", len(weeks) >= a.min_active_weeks)]
    print("\nChecks:")
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print("\nNOTE: source and licence cannot be verified by code. Record them yourself in .env / data/README.md.")
    ok = all(p for _, p in checks)
    print("\nRESULT:", "dataset meets the minimum requirements" if ok else "dataset does NOT meet the requirements")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
