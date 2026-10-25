"""Genuine MongoDB MapReduce jobs.

The JavaScript below is sent to the MongoDB SERVER, which runs it (the `mapReduce` database command).
Nothing here uses aggregation pipelines or Pandas to produce the results.

MapReduce in one paragraph (for beginners)
  MAP    : runs once per input document and calls emit(key, value) zero or more times.
  GROUP  : MongoDB gathers all values that share the same key.
  REDUCE : receives (key, [values...]) and folds them into ONE value. It must return the same
           shape it receives, because MongoDB may call it repeatedly on partial results.
  FINALIZE (optional): runs once per key at the very end to tidy the final value.

Output format: documents shaped {_id: <key>, value: <reduced value>}.
Compatibility: verified on MongoDB 4.2.15 with PyMongo 4.10.1. MapReduce is deprecated from
MongoDB 5.0 onward, so run scripts/verify_mapreduce.py on any other server version first.
"""
import logging
import time
from datetime import datetime, timezone

from bson.code import Code
from pymongo.errors import PyMongoError

from src.database import (TOPIC_MENTIONS, TOPIC_PERIOD_COUNTS, TOPIC_SUMMARY, save_metadata)
from src.periods import period_start

log = logging.getLogger(__name__)


class MapReduceError(Exception):
    """Raised when the MongoDB server rejects or fails a MapReduce job."""


# ----------------------------------------------------------------------------------------------
# JOB 1  -  Topic mentions by time period
# Purpose : count mentions of each topic in each time period.
# Input   : topic_mentions   (one document per topic mention: {post_id, topic, created_at})
# Output  : topic_period_counts  ->  {_id: {topic, period}, value: mention_count}
# ----------------------------------------------------------------------------------------------
JOB1_MAP = Code("""
function () {
    // `this` is one topic_mentions document. `granularity` is passed in through `scope`.
    var d = this.created_at;
    var year = d.getUTCFullYear(), month = d.getUTCMonth(), day = d.getUTCDate();
    function pad(n) { return n < 10 ? "0" + n : "" + n; }

    var periodKey;
    if (granularity === "month") {
        periodKey = year + "-" + pad(month + 1) + "-01";
    } else if (granularity === "day") {
        periodKey = year + "-" + pad(month + 1) + "-" + pad(day);
    } else {                                   // week: use the Monday of the week
        var t = new Date(Date.UTC(year, month, day));
        var daysSinceMonday = (t.getUTCDay() + 6) % 7;
        t = new Date(t.getTime() - daysSinceMonday * 86400000);
        periodKey = t.getUTCFullYear() + "-" + pad(t.getUTCMonth() + 1) + "-" + pad(t.getUTCDate());
    }
    // Composite key (topic, period); each mention counts as 1.
    emit({topic: this.topic, period: periodKey}, 1);
}
""")

JOB1_REDUCE = Code("""
function (key, values) {
    // `values` holds many 1s (or partial sums). Adding them gives the mention count.
    return Array.sum(values);
}
""")

# ----------------------------------------------------------------------------------------------
# JOB 2  -  Topic popularity summary
# Purpose : one summary row per topic across its whole history.
# Input   : topic_period_counts (output of Job 1)
# Output  : topic_summary -> {_id: topic, value: {total, periods, max_count, peak_period, ...}}
# ----------------------------------------------------------------------------------------------
JOB2_MAP = Code("""
function () {
    // One input document = one (topic, period) count. Emit a mini-summary keyed by topic.
    var c = this.value;
    emit(this._id.topic, {
        total: c, periods: 1, max_count: c, min_count: c, sum_sq: c * c,
        first_period: this._id.period, last_period: this._id.period, peak_period: this._id.period
    });
}
""")

JOB2_REDUCE = Code("""
function (key, values) {
    // Merge mini-summaries. The result has the SAME shape as the emitted values.
    var out = {
        total: values[0].total, periods: values[0].periods, max_count: values[0].max_count,
        min_count: values[0].min_count, sum_sq: values[0].sum_sq, first_period: values[0].first_period,
        last_period: values[0].last_period, peak_period: values[0].peak_period
    };
    for (var i = 1; i < values.length; i++) {
        var v = values[i];
        out.total += v.total;
        out.periods += v.periods;
        out.sum_sq += v.sum_sq;
        if (v.max_count > out.max_count || (v.max_count === out.max_count && v.peak_period < out.peak_period)) {
            out.max_count = v.max_count;
            out.peak_period = v.peak_period;
        }
        if (v.min_count < out.min_count) out.min_count = v.min_count;
        if (v.first_period < out.first_period) out.first_period = v.first_period;
        if (v.last_period > out.last_period) out.last_period = v.last_period;
    }
    return out;
}
""")

JOB2_FINALIZE = Code("""
function (key, v) {
    // Runs once per topic after reducing. Average and spread over the ACTIVE periods only.
    v.mean_per_active_period = v.total / v.periods;
    var variance = v.sum_sq / v.periods - v.mean_per_active_period * v.mean_per_active_period;
    v.std_per_active_period = Math.sqrt(variance > 0 ? variance : 0);
    return v;
}
""")


def _run_command(db, job_name: str, command_kwargs: dict) -> dict:
    started = time.time()
    try:
        result = db.command("mapReduce", **command_kwargs)
    except PyMongoError as error:
        raise MapReduceError(
            f"MongoDB rejected {job_name}: {error}. Check the server version with "
            "`python scripts/verify_mapreduce.py` - MapReduce needs a server that still supports it."
        ) from error
    if result.get("ok") != 1:
        raise MapReduceError(f"{job_name} returned ok={result.get('ok')}: {result}")
    counts = result.get("counts", {})
    return {"input": counts.get("input"), "emit": counts.get("emit"), "output": counts.get("output"),
            "seconds": round(time.time() - started, 2)}


def run_job1_topic_period_counts(db, granularity: str) -> dict:
    if granularity not in ("day", "week", "month"):
        raise ValueError("granularity must be 'day', 'week' or 'month'")
    stats = _run_command(db, "Job 1 (topic mentions by period)", {
        "mapReduce": TOPIC_MENTIONS, "map": JOB1_MAP, "reduce": JOB1_REDUCE,
        "out": {"replace": TOPIC_PERIOD_COUNTS}, "scope": {"granularity": granularity}})
    db[TOPIC_PERIOD_COUNTS].create_index("_id.topic")  # speeds up per-topic reads
    return stats


def run_job2_topic_summary(db) -> dict:
    return _run_command(db, "Job 2 (topic popularity summary)", {
        "mapReduce": TOPIC_PERIOD_COUNTS, "map": JOB2_MAP, "reduce": JOB2_REDUCE,
        "finalize": JOB2_FINALIZE, "out": {"replace": TOPIC_SUMMARY}})


def validate_mapreduce_output(db, granularity: str, sample_topics: int = 25) -> dict:
    """Independent checks that do NOT rely on MapReduce.

    1. Sum of all Job 1 counts must equal the number of topic_mentions documents.
    2. For the most-mentioned topics, recount mentions in plain Python and compare per period.
    3. Job 2 totals must equal the sum of Job 1 counts per topic.
    """
    problems = []
    mention_total = db[TOPIC_MENTIONS].count_documents({})
    summary_docs = list(db[TOPIC_SUMMARY].find().sort("value.total", -1))
    count_total = sum(int(d["value"]["total"]) for d in summary_docs)
    if mention_total != count_total:
        problems.append(f"Total mismatch: {mention_total} mentions vs {count_total} in topic_summary")
    job1_total = 0
    for doc in db[TOPIC_PERIOD_COUNTS].find({}, {"value": 1}):
        job1_total += int(doc["value"])
    if job1_total != mention_total:
        problems.append(f"Job 1 total {job1_total} != mentions {mention_total}")

    checked = 0
    for summary in summary_docs[:sample_topics]:
        topic = summary["_id"]
        expected = {}
        for mention in db[TOPIC_MENTIONS].find({"topic": topic}, {"created_at": 1}):
            key = period_start(mention["created_at"], granularity)
            expected[key] = expected.get(key, 0) + 1
        actual = {d["_id"]["period"]: int(d["value"])
                  for d in db[TOPIC_PERIOD_COUNTS].find({"_id.topic": topic})}
        if expected != actual:
            problems.append(f"Per-period counts differ for topic '{topic}'")
        if sum(expected.values()) != int(summary["value"]["total"]):
            problems.append(f"Job 2 total differs for topic '{topic}'")
        checked += 1
    return {"valid": not problems, "problems": problems, "topics_checked_independently": checked,
            "mention_total": mention_total}


def run_all_jobs(db, granularity: str, server_version: str = "unknown") -> dict:
    """Run both jobs, validate, and store the status that the dashboard displays."""
    status = {"granularity": granularity, "server_version": server_version,
              "ran_at": datetime.now(timezone.utc), "jobs": {}, "status": "failed"}
    try:
        status["jobs"]["job1_topic_period_counts"] = run_job1_topic_period_counts(db, granularity)
        status["jobs"]["job2_topic_summary"] = run_job2_topic_summary(db)
        status["validation"] = validate_mapreduce_output(db, granularity)
        status["status"] = "success" if status["validation"]["valid"] else "completed_with_validation_errors"
    except MapReduceError as error:
        status["error"] = str(error)
        save_metadata(db, "mapreduce_status", status)
        raise
    save_metadata(db, "mapreduce_status", status)
    return status
