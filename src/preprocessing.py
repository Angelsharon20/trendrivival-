"""Stage: clean `raw_posts` -> `clean_posts` and extract `topic_mentions`.

TIMEZONE STRATEGY: every timestamp is converted to UTC. Timestamps without a timezone are
ASSUMED to already be UTC. Numeric timestamps are Unix epoch seconds (or milliseconds when > 1e11).

Nothing is removed silently: every rejected record is counted by reason in the summary.
"""
import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timezone

import pandas as pd

from src.database import CLEAN_POSTS, RAW_POSTS, TOPIC_MENTIONS, ensure_indexes
from src.ingestion import is_blank
from src.topic_extraction import URL_RE, extract_topics

log = logging.getLogger(__name__)
MIN_VALID_YEAR, MAX_VALID_YEAR = 2004, 2100  # social media did not exist before this


def normalise_timestamp(value):
    """Return a timezone-aware UTC datetime, or None when the value is missing/invalid."""
    if is_blank(value):
        return None
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
        elif isinstance(value, str) and re.fullmatch(r"\d{9,13}(\.\d+)?", value.strip()):
            number = float(value.strip())
        else:
            number = None
        if number is not None:
            seconds = number / 1000.0 if number > 1e11 else number
            stamp = pd.Timestamp(seconds, unit="s", tz="UTC")
        else:
            stamp = pd.to_datetime(value, utc=True, errors="coerce")
        if stamp is None or pd.isna(stamp):
            return None
        result = stamp.to_pydatetime()
    except (ValueError, OverflowError, TypeError):
        return None
    if not (MIN_VALID_YEAR <= result.year <= MAX_VALID_YEAR):
        return None
    return result


def normalise_text(text) -> str:
    """Light cleaning: Unicode normalisation, URLs removed, whitespace collapsed. Case is kept."""
    if is_blank(text):
        return ""
    cleaned = unicodedata.normalize("NFKC", str(text))
    cleaned = URL_RE.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def content_hash(clean_text: str, created_at, topics: list) -> str:
    """Fingerprint used to detect duplicate posts (same text, same moment, same topics)."""
    payload = f"{clean_text.lower()}|{created_at.isoformat()}|{','.join(sorted(topics))}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def clean_record(data: dict, settings, topic_mode: str) -> dict:
    """Clean ONE raw record. Returns {'ok': bool, 'reason': str|None, 'clean': dict, 'topics': list, 'flags': dict}"""
    raw_text = data.get(settings.col_text) if settings.col_text else None
    raw_tags = data.get(settings.col_hashtags) if settings.col_hashtags else None
    created_at = normalise_timestamp(data.get(settings.col_date))
    clean_text = normalise_text(raw_text)
    topics = extract_topics(clean_text, raw_tags, topic_mode) if (clean_text or not is_blank(raw_tags)) else []
    flags = {"missing_text": not clean_text, "missing_hashtags": is_blank(raw_tags) if settings.col_hashtags else False,
             "missing_timestamp": is_blank(data.get(settings.col_date))}

    if created_at is None:
        return {"ok": False, "reason": "missing_timestamp" if flags["missing_timestamp"] else "invalid_timestamp",
                "flags": flags, "topics": [], "clean": None}
    if not clean_text and is_blank(raw_tags):
        return {"ok": False, "reason": "empty_text", "flags": flags, "topics": [], "clean": None}
    if not topics:
        return {"ok": False, "reason": "no_topic_found", "flags": flags, "topics": [], "clean": None}
    clean = {"text_original": None if is_blank(raw_text) else str(raw_text), "text_clean": clean_text,
             "created_at": created_at, "topics": topics}
    return {"ok": True, "reason": None, "flags": flags, "topics": topics, "clean": clean}


def choose_topic_mode(db, settings, sample_size: int = 2000) -> str:
    """'auto' -> hashtag mode if >=10% of sampled posts contain hashtags, else keyword mode."""
    if settings.topic_mode in ("hashtag", "keyword"):
        return settings.topic_mode
    sample = list(db[RAW_POSTS].find({}, {"data": 1}).limit(sample_size))
    if not sample:
        return "hashtag"
    with_tags = sum(1 for doc in sample if extract_topics(
        doc["data"].get(settings.col_text) if settings.col_text else None,
        doc["data"].get(settings.col_hashtags) if settings.col_hashtags else None, "hashtag"))
    share = with_tags / len(sample)
    mode = "hashtag" if share >= 0.10 else "keyword"
    log.info("Auto topic mode: %.1f%% of sampled posts have hashtags -> using '%s'", share * 100, mode)
    return mode


def preprocess_posts(db, settings) -> dict:
    """Run the whole cleaning stage. Safe to re-run: clean_posts and topic_mentions are rebuilt."""
    db[CLEAN_POSTS].drop()
    db[TOPIC_MENTIONS].drop()
    topic_mode = choose_topic_mode(db, settings)
    original_count = db[RAW_POSTS].count_documents({})
    summary = {"original_count": original_count, "topic_mode_used": topic_mode, "timezone": "UTC",
               "rejected": {}, "duplicates": 0, "missing_text": 0, "missing_hashtags": 0,
               "missing_timestamp": 0, "retained": 0, "topic_mentions": 0}
    seen_hashes, post_buffer, mention_buffer = set(), [], []
    first_date = last_date = None

    def flush():
        if post_buffer:
            db[CLEAN_POSTS].insert_many(post_buffer, ordered=False)
            post_buffer.clear()
        if mention_buffer:
            db[TOPIC_MENTIONS].insert_many(mention_buffer, ordered=False)
            mention_buffer.clear()

    for number, document in enumerate(db[RAW_POSTS].find({}, {"data": 1}).batch_size(1000), start=1):
        result = clean_record(document["data"], settings, topic_mode)
        for flag, name in (("missing_text", "missing_text"), ("missing_hashtags", "missing_hashtags"),
                           ("missing_timestamp", "missing_timestamp")):
            summary[name] += int(result["flags"][flag])
        if not result["ok"]:
            summary["rejected"][result["reason"]] = summary["rejected"].get(result["reason"], 0) + 1
            continue
        clean = result["clean"]
        digest = content_hash(clean["text_clean"], clean["created_at"], result["topics"])
        if digest in seen_hashes:
            summary["duplicates"] += 1
            summary["rejected"]["duplicate"] = summary["rejected"].get("duplicate", 0) + 1
            continue
        seen_hashes.add(digest)
        clean["_id"] = document["_id"]
        post_buffer.append(clean)
        for topic in result["topics"]:
            mention_buffer.append({"post_id": document["_id"], "topic": topic, "created_at": clean["created_at"]})
        summary["retained"] += 1
        summary["topic_mentions"] += len(result["topics"])
        stamp = clean["created_at"]
        first_date = stamp if first_date is None or stamp < first_date else first_date
        last_date = stamp if last_date is None or stamp > last_date else last_date
        if len(post_buffer) >= settings.batch_size:
            flush()
        if number % 50000 == 0:
            log.info("Cleaned %s of %s records", number, original_count)
    flush()
    ensure_indexes(db)
    summary["rejected_total"] = sum(summary["rejected"].values())
    summary["final_usable_count"] = summary["retained"]
    summary["date_start"] = first_date
    summary["date_end"] = last_date
    summary["distinct_topics_in_mentions"] = len(db[TOPIC_MENTIONS].distinct("topic")) if summary["retained"] else 0
    assert summary["retained"] + summary["rejected_total"] == original_count, "Record accounting mismatch"
    return summary
