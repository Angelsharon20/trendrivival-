# Trend Revival - Social Media Trend Comeback Detection Using MongoDB MapReduce

A Big Data Analytics project. It imports a social media dataset into MongoDB, cleans it, extracts topics, runs
**genuine MongoDB MapReduce jobs** to count topic mentions per time period, and applies a transparent rule-based
algorithm to find **potential comebacks** (earlier peak -> decline -> quiet period -> renewed attention).
A Streamlit dashboard shows the results.

## Honest status (read this first)
| Item | Status |
|---|---|
| Full pipeline code (validate, ingest, preprocess, MapReduce, detect, dashboard) | Written |
| Automated tests (40) | **Pass** on Linux with MongoDB 4.2.15 + PyMongo 4.10.1 + Python 3.12 |
| MapReduce executes on a real MongoDB server | **Verified** (MongoDB 4.2.15, Linux) |
| Real dataset with >= 50,000 usable records | **NOT included. You must supply and validate one** (`data/README.md`) |
| Results on real data | **Not produced yet** - nothing in this repo claims findings |
| Tested on Windows | **No** (instructions below are standard but unverified; `verify_mapreduce.py` checks your machine) |
| Other MongoDB versions (5.0+) | **Unverified**. MapReduce is deprecated from 5.0; run `verify_mapreduce.py` |

Synthetic data exists **only inside `tests/`**. The pipeline itself never fabricates records.

## Pipeline
```
dataset file -> validate_dataset -> ingest_data -> raw_posts -> preprocess_data -> clean_posts + topic_mentions
 -> run_mapreduce (Job 1: topic_period_counts, Job 2: topic_summary) -> detect_comebacks -> comeback_results -> app.py
```
| Stage | Command | Input -> Output |
|---|---|---|
| Verify MapReduce | `python scripts/verify_mapreduce.py` | server -> PASS/FAIL |
| Validate dataset | `python scripts/validate_dataset.py` | file -> report |
| Ingest | `python scripts/ingest_data.py` | file -> `raw_posts` |
| Preprocess | `python scripts/preprocess_data.py` | `raw_posts` -> `clean_posts`, `topic_mentions` |
| MapReduce | `python scripts/run_mapreduce.py` | `topic_mentions` -> `topic_period_counts` -> `topic_summary` |
| Detect | `python scripts/detect_comebacks.py` | MapReduce output -> `comeback_results` |
| Dashboard | `streamlit run app.py` | MongoDB -> browser |

## Windows setup (PowerShell)
**1. Install Python** 3.11 or 3.12 from python.org (tick "Add python.exe to PATH"). Check: `python --version`

**2. Open the project folder** (change the path to where you unzipped it):
```powershell
cd C:\Users\YourName\Documents\trend-revival
```
**3. Create and activate a virtual environment, install packages**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again.
`requirements.txt` pins **PyMongo 4.10.1** on purpose: the newest PyMongo refuses MongoDB 4.2 ("requires 4.4+").

**4. Install MongoDB Community (a version that supports MapReduce).** Open the MongoDB Download Center ->
Community Server -> *Archived releases* and choose **4.4.x** (or 4.2.x) for Windows. (Version 4.2 was the one verified
in testing; 4.4 is expected to work but is unverified.) Docker is **not** needed. Two options:
- *Installer (.msi)*: run it, accept the defaults ("Install as a Service" keeps MongoDB running in the background).
- *ZIP, no admin rights*: unzip it, then:
```powershell
mkdir C:\mongo_data
C:\path\to\mongodb\bin\mongod.exe --dbpath C:\mongo_data
```
Leave that window open - it is the database server.

**5. Configure**
```powershell
copy .env.example .env
notepad .env
```
Set `DATASET_PATH`, the `COL_*` column names that match **your** file, and `DATASET_NAME/SOURCE/LICENSE`.

**6. Verify MapReduce works on your machine** (stop here if it says FAIL)
```powershell
python scripts/verify_mapreduce.py
```
**7-13. Run the pipeline in order**
```powershell
python scripts/validate_dataset.py
python scripts/ingest_data.py
python scripts/preprocess_data.py
python scripts/run_mapreduce.py
python scripts/detect_comebacks.py
streamlit run app.py
```
**14. Run the tests** (needs MongoDB running; integration tests skip themselves if it is not):
```powershell
python -m pytest -v
```
Logs are written to `logs\`.

## Common errors
| Message | Meaning / fix |
|---|---|
| `Cannot connect to MongoDB ... Connection refused` | `mongod` is not running. Start it (step 4). |
| `reports wire version 8, but this version of PyMongo requires at least 9` | PyMongo too new for MongoDB 4.2. `pip install -r requirements.txt` (pinned). |
| `FAIL: the server rejected MapReduce` | Server version too new/unsupported. Install 4.4/4.2. |
| `These configured columns are not in the file` | Fix `COL_*` in `.env` to match the columns printed. |
| `dataset does NOT meet the requirements` | Too few records, too short a time span, or too few active weeks. Choose another dataset - do not lower the bar silently. |
| `running scripts is disabled on this system` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `MapReduce has not completed successfully` (dashboard) | Run `python scripts/run_mapreduce.py` |

## Method summary
* **Time zone:** everything is UTC; timestamps without a zone are assumed UTC.
* **Topics:** hashtags (column and `#tags` in text) or text keywords (stop-words removed); `TOPIC_MODE=auto` picks hashtags if >= 10% of sampled posts have them.
* **Periods:** week (Monday start) by default; `GRANULARITY=day|week|month`. The JavaScript map function and the Python helper use the same rule (tested).
* **MapReduce Job 1:** key `(topic, period)`, value 1, reduce = sum. **Job 2:** per-topic total, active periods, max/min, peak period, mean and std over active periods.
* **Validation:** sums are compared with the number of mentions; the top topics are recounted in plain Python and compared per period.
* **Comeback algorithm:** see the docstring in `src/comeback_detection.py`. Thresholds live in `detection_params.json` and in the dashboard sidebar. They are practical defaults, **not scientific constants** - tune them after looking at your real data.
* **Zero baseline:** divisor falls back to `baseline_floor` (1 mention) so growth is never infinite.

## Limitations
Keyword/hashtag matching has no semantic understanding. The data is historical, so this does not detect *current* trends.
A detected pattern means renewed mentions in the dataset only. The final period may be incomplete. The dashboard computes
detection on up to N top topics (default 5000) for speed; `detect_comebacks.py` analyses every topic above the minimum.
JSON-array files are loaded fully into memory (use CSV or JSON-lines for large files).

## Project layout
`app.py` dashboard | `config.py` settings | `detection_params.json` thresholds | `scripts/` pipeline commands |
`src/` logic (`mapreduce_jobs.py`, `comeback_detection.py`, `preprocessing.py`, ...) | `tests/` pytest | `reports/` academic documents
