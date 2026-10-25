# College Report Outline - Trend Revival

Fill each section from your **actual execution results**. Items in [BRACKETS] are placeholders - do not invent values.

1. **Title Page** - project title, your name, student ID, department, institution, guide/faculty, date.
2. **Abstract** (150-250 words) - problem, MongoDB MapReduce approach, dataset [NAME, N records], headline result [X potential comebacks at thresholds ...], limitation.
3. **Introduction** - social media trends rise and fade; why resurgences matter; why Big Data tools are used.
4. **Problem Statement** - detect topics that peaked, declined, stayed quiet, then returned, and distinguish them from continuous growth.
5. **Objectives** - the 14 mandatory requirements, restated in your words.
6. **Dataset Description** - source [URL/citation], licence [..], download date, record count [original / usable], columns, date range, missing-value rates, limitations (use `validate_dataset.py` output).
7. **Tools and Technologies** - Python, MongoDB [version], PyMongo [version], Pandas, Streamlit, Plotly, pytest; justify each in one line.
8. **System Architecture** - pipeline diagram (README), collections table, data flow.
9. **Methodology** - overall approach, time granularity [week], UTC strategy, topic extraction method, parameter selection process.
10. **Data Ingestion and Preprocessing** - ingestion counters, cleaning summary table (original, duplicates, invalid timestamps, empty text, retained, rejected, final), topic mode used.
11. **MongoDB MapReduce Implementation** - explain MapReduce; Job 1 and Job 2 (purpose, input, map, reduce, output); version compatibility note (deprecated from 5.0); validation procedure and result.
12. **Comeback Detection Algorithm** - the five rules, formulas (decline %, growth %), zero-baseline rule, parameter table with values used, why not a single percentage rule.
13. **Results and Visualisations** - KPIs, top topics, 2-3 detected timelines, comparison chart, sensitivity of results to thresholds. Use "potential comeback" wording only.
14. **Testing and Validation** - pytest results [N passed], synthetic comeback vs steady growth tests, MapReduce vs independent Python counts.
15. **Limitations** - semantics, thresholds, historical-only, incomplete last period, dataset bias, no ground truth for "real" comebacks.
16. **Conclusion** - what was achieved, what the results do and do not show, future work (lemmatisation, embeddings, seasonality handling, live data source).
17. **References** - cite ONLY sources you actually used: the dataset, MongoDB documentation, library documentation. Do not add citations you have not read.
18. **Appendix** - source code listing (key files), execution evidence (see `execution_evidence_checklist.md`), full parameter file.
