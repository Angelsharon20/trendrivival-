# Execution Evidence Checklist (capture these for your report/viva)

Save screenshots in a folder `evidence/` (not committed). Show the command AND its output in each screenshot.

| # | Evidence | How |
|---|---|---|
| 1 | Python and MongoDB versions | `python --version`; verify script output |
| 2 | **MapReduce compatibility PASS** | `python scripts/verify_mapreduce.py` |
| 3 | Dataset validation report | `python scripts/validate_dataset.py` (record count, date range, PASS lines) |
| 4 | Dataset source page + licence | browser screenshot of the dataset page |
| 5 | Ingestion summary | `python scripts/ingest_data.py` |
| 6 | Re-run ingestion (no duplicates) | run it again; `skipped_duplicates` equals inserted before |
| 7 | Cleaning summary | `python scripts/preprocess_data.py` |
| 8 | MongoDB collections with counts | MongoDB Compass (or `mongosh`) showing raw_posts, clean_posts, topic_mentions, topic_period_counts, topic_summary, comeback_results |
| 9 | Sample MapReduce output documents | Compass: a few `topic_period_counts` docs |
| 10 | MapReduce status + validation | `python scripts/run_mapreduce.py` output |
| 11 | Detection output | `python scripts/detect_comebacks.py` |
| 12 | Dashboard pages (5 screenshots) | Overview, Trend Timeline (a detected topic), Comeback Detector, Topic Comparison, Data & Methodology |
| 13 | Threshold change demo | detector table before/after moving a slider |
| 14 | Tests | `python -m pytest -v` full output |
| 15 | Logs | files in `logs\` |
| 16 | Source code | screenshots/listing of `src/mapreduce_jobs.py` and `src/comeback_detection.py` |
