"""Read-only helpers that turn MapReduce output into series, tables and KPIs."""
from datetime import datetime, timezone

import pandas as pd

from src.comeback_detection import STATUS_COMEBACK, DetectionParams, detect_comeback
from src.database import (CLEAN_POSTS, COMEBACK_RESULTS, RAW_POSTS, TOPIC_PERIOD_COUNTS, TOPIC_SUMMARY,
                          get_metadata, save_metadata)
from src.periods import period_range


def build_dense_series(period_counts: dict, start: str, end: str, granularity: str):
    """Fill missing periods with 0 so every period between start and end has a value."""
    periods = period_range(start, end, granularity)
    return periods, [int(period_counts.get(period, 0)) for period in periods]


def global_last_period(db):
    doc = db[TOPIC_SUMMARY].find_one(sort=[("value.last_period", -1)])
    return doc["value"]["last_period"] if doc else None


def global_first_period(db):
    doc = db[TOPIC_SUMMARY].find_one(sort=[("value.first_period", 1)])
    return doc["value"]["first_period"] if doc else None


def summary_table(db, min_total: int = 0, limit: int = 0) -> pd.DataFrame:
    cursor = db[TOPIC_SUMMARY].find({"value.total": {"$gte": min_total}}).sort("value.total", -1)
    if limit:
        cursor = cursor.limit(limit)
    rows = []
    for doc in cursor:
        v = doc["value"]
        rows.append({"topic": doc["_id"], "total_mentions": int(v["total"]), "active_periods": int(v["periods"]),
                     "peak_count": int(v["max_count"]), "peak_period": v["peak_period"],
                     "first_period": v["first_period"], "last_period": v["last_period"],
                     "mean_per_active_period": round(v["mean_per_active_period"], 2),
                     "std_per_active_period": round(v["std_per_active_period"], 2)})
    return pd.DataFrame(rows)


def load_series(db, topics: list, granularity: str, chunk: int = 500) -> dict:
    """Return {topic: (periods, counts)} zero-filled from each topic's first period to the dataset end."""
    end = global_last_period(db)
    if not end or not topics:
        return {}
    firsts = {d["_id"]: d["value"]["first_period"] for d in db[TOPIC_SUMMARY].find({"_id": {"$in": topics}})}
    raw = {topic: {} for topic in topics}
    for start in range(0, len(topics), chunk):
        part = topics[start:start + chunk]
        for doc in db[TOPIC_PERIOD_COUNTS].find({"_id.topic": {"$in": part}}):
            raw[doc["_id"]["topic"]][doc["_id"]["period"]] = int(doc["value"])
    return {t: build_dense_series(raw[t], firsts[t], end, granularity) for t in topics if t in firsts}


def run_detection(db, params: DetectionParams, granularity: str, max_topics: int = 0) -> list:
    """Run the algorithm on every topic with enough mentions. Returns a list of result dicts."""
    table = summary_table(db, params.min_total_mentions, max_topics)
    series = load_series(db, list(table["topic"]), granularity) if len(table) else {}
    return [detect_comeback(counts, periods, params, topic) for topic, (periods, counts) in series.items()]


def store_results(db, results: list, params: DetectionParams, granularity: str) -> int:
    from dataclasses import asdict
    db[COMEBACK_RESULTS].delete_many({})
    if results:
        db[COMEBACK_RESULTS].insert_many([dict(r) for r in results])
    save_metadata(db, "detection_run", {"parameters": asdict(params), "granularity": granularity,
                                        "topics_analysed": len(results),
                                        "potential_comebacks": sum(r["status"] == STATUS_COMEBACK for r in results),
                                        "ran_at": datetime.now(timezone.utc)})
    return len(results)


def results_table(results: list) -> pd.DataFrame:
    rows = [{"topic": r["topic"], "status": r["status"], "total_mentions": r["total_mentions"],
             "peak_count": r["peak_count"], "decline_percentage": r["decline_percentage"],
             "quiet_periods": r["quiet_periods"], "baseline_count": r["baseline_count"],
             "current_count": r["current_count"], "growth_percentage": r["growth_percentage"],
             "resurgence_period": r["resurgence_period"], "n_events": r["n_events"]} for r in results]
    return pd.DataFrame(rows)


def overview_kpis(db) -> dict:
    """All KPIs come from stored processing results. Missing pieces are returned as None."""
    prep = get_metadata(db, "preprocessing_summary") or {}
    ingest = get_metadata(db, "ingestion_summary") or {}
    return {
        "source_records": prep.get("original_count") or ingest.get("raw_posts_in_db") or db[RAW_POSTS].estimated_document_count(),
        "usable_records": prep.get("final_usable_count"),
        "distinct_topics": db[TOPIC_SUMMARY].estimated_document_count(),
        "potential_comebacks": db[COMEBACK_RESULTS].count_documents({"status": STATUS_COMEBACK}),
        "date_start": prep.get("date_start"), "date_end": prep.get("date_end"),
    }
