"""Run the comeback detection algorithm on the MapReduce output and store comeback_results."""
import argparse
import sys

import _bootstrap  # noqa: F401

from config import DETECTION_PARAMS_FILE, load_settings
from src.analytics import results_table, run_detection, store_results
from src.comeback_detection import STATUS_COMEBACK, load_params
from src.database import TOPIC_SUMMARY, check_connection, get_client, get_metadata


def main() -> int:
    _bootstrap.setup_logging("detection")
    settings = load_settings()
    ap = argparse.ArgumentParser(description="Thresholds come from detection_params.json; override on the command line.")
    for name in ("min_total_mentions", "min_peak_count", "min_quiet_periods", "min_current_count", "resurgence_window", "min_posts_in_resurgence"):
        ap.add_argument(f"--{name.replace('_', '-')}", type=int)
    for name in ("min_decline_pct", "min_growth_pct"):
        ap.add_argument(f"--{name.replace('_', '-')}", type=float)
    args = ap.parse_args()
    overrides = {k: v for k, v in vars(args).items() if v is not None}
    client = get_client(settings)
    ok, info = check_connection(client)
    if not ok:
        print(f"Cannot connect to MongoDB: {info}")
        return 1
    db = client[settings.db_name]
    status = get_metadata(db, "mapreduce_status")
    if not status or status.get("status") != "success" or db[TOPIC_SUMMARY].estimated_document_count() == 0:
        print("MapReduce has not completed successfully. Run: python scripts/run_mapreduce.py")
        return 1
    params = load_params(DETECTION_PARAMS_FILE, overrides)
    results = run_detection(db, params, status["granularity"])
    store_results(db, results, params, status["granularity"])
    table = results_table(results)
    found = table[table["status"] == STATUS_COMEBACK].sort_values("growth_percentage", ascending=False)
    print(f"\nTopics analysed: {len(results)} | potential comebacks: {len(found)} | granularity: {status['granularity']}")
    print(found.head(20).to_string(index=False) if len(found) else "No potential comebacks with these thresholds - try loosening them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
