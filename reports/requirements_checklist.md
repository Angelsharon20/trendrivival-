# Requirements Rubric - status of every mandatory requirement

Legend: **DONE** = implemented and verified here | **CODE READY** = implemented and tested on synthetic test data only, needs your real dataset | **YOU** = only you can do this | **UNVERIFIED** = not tested in this environment

## A. The 14 mandatory academic requirements
| # | Requirement | Status | Evidence / what remains |
|---|---|---|---|
| 1 | Real dataset, >= 50,000 usable records | **YOU** | No dataset was available in the build environment. Supply one; `validate_dataset.py` checks it. Synthetic data is never used as the final dataset. |
| 2 | Unstructured / semi-structured data | **CODE READY** | Text + hashtag columns supported (CSV / JSONL / JSON). |
| 3 | Document source, count, columns, date range, limitations | **YOU** | Validator prints count/columns/range; fill `DATASET_*` in `.env` and `reports/results_template.md`. |
| 4 | Import into MongoDB | **CODE READY** | `scripts/ingest_data.py`; batch, re-runnable, counts inserted/skipped/rejected. Tested (tests/test_preprocessing.py, test_pipeline_e2e.py). |
| 5 | Preprocess and clean | **CODE READY** | `src/preprocessing.py`; UTC, dedupe, missing/empty handling, per-reason counts, record accounting assertion. Tested. |
| 6 | Genuine MongoDB MapReduce | **DONE** | `mapReduce` command executed by MongoDB 4.2.15 (tests/test_mapreduce.py); no aggregation pipeline or Pandas used for the jobs. |
| 7 | Topic popularity across periods | **CODE READY** | Job 1 (topic x period counts), Job 2 (per-topic summary); validated against independent Python counts in tests. |
| 8 | Documented comeback algorithm | **CODE READY** | `src/comeback_detection.py` docstring + 12 tests (known pattern detected, steady growth not flagged). Thresholds untuned for real data. |
| 9 | Visualisations from actual processed data | **CODE READY** | Plotly charts read MongoDB only. Verified on synthetic fixture; real-data screenshots remain. |
| 10 | Interactive dashboard | **DONE** | 5 pages, threshold controls; AppTest renders all pages, empty state and connection-error state. |
| 11 | Executable code and automated tests | **DONE** | `python -m pytest -v` -> 40 passed (Linux, MongoDB 4.2.15, PyMongo 4.10.1, Python 3.12). |
| 12 | Install instructions + evidence instructions | **DONE** (Windows **UNVERIFIED**) | README, `execution_evidence_checklist.md`. |
| 13 | Report outline + 7-10 slide outline | **DONE** | `report_outline.md`, `presentation_outline.md` (9 slides). |
| 14 | Demonstrable on a student's laptop | **UNVERIFIED** | Run `verify_mapreduce.py` on your Windows machine; needs your dataset. |

## B. Final acceptance criteria (section 18 of the brief)
| Criterion | Status |
|---|---|
| Real dataset >= 50,000 usable records verified | **NOT MET - needs your dataset** |
| Provenance and date coverage documented | **NOT MET - needs your dataset** |
| Ingestion succeeds | Met on test data; run on real data |
| Preprocessing succeeds + summary | Met on test data; run on real data |
| MongoDB contains relevant collections | Met on test data |
| Genuine MapReduce executes | **Met** |
| MapReduce output validated | **Met** (automatic validation after every run) |
| Comeback detection passes automated tests | **Met** |
| Dashboard displays actual processed results | Met on test data; real-data run pending |
| End-to-end procedure documented | **Met** |
| Report and presentation outlines | **Met** |
| Limitations stated | **Met** |

**The project is NOT complete by the brief's own definition until you supply and validate a real dataset and run the pipeline on it.**

## C. Self-marking guide (typical rubric weights - confirm with your faculty)
| Component | What to show |
|---|---|
| Problem and objectives | report sections 3-5 |
| Dataset and provenance | validation report, source/licence, limitations |
| MapReduce implementation | map/reduce code, execution log, validation |
| Algorithm design | formulas, parameters, tests, threshold sensitivity |
| Results and visualisation | 5 dashboard screenshots from YOUR data |
| Testing | pytest output |
| Documentation and demo | README, report, slides |
