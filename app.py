"""Trend Revival dashboard. Shows ONLY data read from MongoDB; nothing is hard-coded or random.

Run:  streamlit run app.py
"""
import plotly.graph_objects as go
import streamlit as st

from config import DETECTION_PARAMS_FILE, load_settings
from src.analytics import (load_series, overview_kpis, results_table, run_detection, summary_table)
from src.comeback_detection import STATUS_COMEBACK, DetectionParams, detect_comeback, load_params, params_to_dict
from src.database import (COMEBACK_RESULTS, TOPIC_SUMMARY, check_connection, get_client, get_metadata)

st.set_page_config(page_title="Trend Revival", page_icon="📈", layout="wide")
st.markdown("""<style>
.block-container {padding-top: 2rem; max-width: 1250px;}
[data-testid="stMetricValue"] {font-size: 1.7rem;}
h1, h2, h3 {letter-spacing: -0.01em;}
</style>""", unsafe_allow_html=True)
PALETTE = {"line": "#2f5d8a", "peak": "#c0392b", "quiet": "#b8c4d0", "resurgence": "#1e8e5a"}
LABEL = {"day": "daily", "week": "weekly", "month": "monthly"}


@st.cache_resource
def connect(uri: str):
    """One MongoDB client per connection string (cached so reruns are fast)."""
    return get_client(load_settings(), timeout_ms=3000)


settings = load_settings()
client = connect(settings.mongodb_uri)
ok, info = check_connection(client)
if not ok:
    st.title("Trend Revival")
    st.error(f"Cannot connect to MongoDB at `{settings.mongodb_uri}`.\n\n{info}")
    st.info("Start MongoDB first (README, section 'Start MongoDB'), then refresh this page.")
    st.stop()
db = client[settings.db_name]

ingest = get_metadata(db, "ingestion_summary")
prep = get_metadata(db, "preprocessing_summary")
mr = get_metadata(db, "mapreduce_status")

st.sidebar.title("📈 Trend Revival")
page = st.sidebar.radio("Page", ["Overview", "Trend Timeline", "Comeback Detector", "Topic Comparison", "Data & Methodology"])
st.sidebar.caption(f"MongoDB {info} · database `{settings.db_name}`")

if not ingest and not prep:
    st.title("Trend Revival")
    st.warning("No dataset has been imported yet.")
    st.code("python scripts/validate_dataset.py\npython scripts/ingest_data.py\npython scripts/preprocess_data.py\n"
            "python scripts/run_mapreduce.py\npython scripts/detect_comebacks.py", language="powershell")
    st.stop()

mapreduce_ready = bool(mr and mr.get("status") == "success" and db[TOPIC_SUMMARY].estimated_document_count() > 0)
granularity = (mr or {}).get("granularity", settings.granularity)
unit = {"day": "days", "week": "weeks", "month": "months"}[granularity]


def need_mapreduce():
    st.warning("MapReduce has not completed successfully, so there are no analytics to show yet.")
    st.code("python scripts/run_mapreduce.py", language="powershell")
    st.stop()


def sidebar_parameters() -> DetectionParams:
    base = params_to_dict(load_params(DETECTION_PARAMS_FILE))
    with st.sidebar.expander("Detection thresholds", expanded=(page in ("Comeback Detector", "Trend Timeline"))):
        values = {
            "min_total_mentions": st.number_input("Min total mentions", 1, 10**7, int(base["min_total_mentions"])),
            "min_peak_count": st.number_input(f"Min peak mentions per {granularity}", 1, 10**6, int(base["min_peak_count"])),
            "min_decline_pct": st.slider("Min decline from peak (%)", 10, 100, int(base["min_decline_pct"])),
            "min_quiet_periods": st.slider(f"Min quiet period ({unit})", 1, 104, int(base["min_quiet_periods"])),
            "min_growth_pct": st.slider("Min resurgence growth (%)", 10, 5000, int(base["min_growth_pct"])),
            "min_current_count": st.number_input(f"Min current mentions per {granularity}", 1, 10**6, int(base["min_current_count"])),
            "resurgence_window": st.slider(f"Resurgence window ({unit})", 1, 12, int(base["resurgence_window"])),
        }
    return DetectionParams(**{**base, **values})


@st.cache_data(show_spinner="Running comeback detection on MapReduce output…", ttl=600)
def cached_detection(params_dict: dict, granularity: str, max_topics: int):
    return run_detection(db, DetectionParams(**params_dict), granularity, max_topics)


@st.cache_data(ttl=600)
def cached_summary(min_total: int, limit: int):
    return summary_table(db, min_total, limit)


def timeline_figure(periods, counts, result, topic):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=periods, y=counts, mode="lines", name="Mentions", line=dict(color=PALETTE["line"], width=2)))
    if result and result["status"] == STATUS_COMEBACK:
        fig.add_vrect(x0=result["quiet_start"], x1=result["quiet_end"], fillcolor=PALETTE["quiet"], opacity=0.35,
                      line_width=0, annotation_text="Quiet period", annotation_position="top left")
        fig.add_trace(go.Scatter(x=[result["peak_period"]], y=[result["peak_count"]], mode="markers+text", name="Earlier peak",
                                 text=["Earlier peak"], textposition="top center", marker=dict(color=PALETTE["peak"], size=11)))
        fig.add_trace(go.Scatter(x=[result["resurgence_period"]], y=[result["current_count"]], mode="markers+text",
                                 name="Renewed attention", text=["Renewed attention"], textposition="top center",
                                 marker=dict(color=PALETTE["resurgence"], size=11)))
        fig.add_vrect(x0=result["peak_period"], x1=result["quiet_start"], fillcolor=PALETTE["peak"], opacity=0.07,
                      line_width=0, annotation_text="Decline", annotation_position="top left")
    fig.update_layout(title=f"{LABEL[granularity].capitalize()} mentions of “{topic}”", template="plotly_white",
                      xaxis_title=f"{granularity.capitalize()} start (UTC)", yaxis_title="Mentions", height=460,
                      margin=dict(l=10, r=10, t=60, b=10), legend=dict(orientation="h", y=-0.2))
    return fig


# ----------------------------------------------------------------------------------------------------------
if page == "Overview":
    st.title("Trend Revival")
    st.caption("Social media trend comeback detection using MongoDB MapReduce")
    if not mapreduce_ready:
        need_mapreduce()
    kpi = overview_kpis(db)
    c = st.columns(5)
    c[0].metric("Source records", f"{kpi['source_records']:,}" if kpi["source_records"] is not None else "n/a")
    c[1].metric("Usable records", f"{kpi['usable_records']:,}" if kpi["usable_records"] is not None else "n/a")
    c[2].metric("Distinct topics", f"{kpi['distinct_topics']:,}")
    c[3].metric("Potential comebacks", f"{kpi['potential_comebacks']:,}" if db[COMEBACK_RESULTS].estimated_document_count() else "run detector")
    span = f"{kpi['date_start']:%Y-%m-%d} → {kpi['date_end']:%Y-%m-%d}" if kpi["date_start"] else "n/a"
    c[4].metric("Date range (UTC)", span)
    top = cached_summary(0, 15)
    fig = go.Figure(go.Bar(x=top["total_mentions"][::-1], y=top["topic"][::-1], orientation="h", marker_color=PALETTE["line"]))
    fig.update_layout(title="Most active topics (total mentions)", template="plotly_white", height=480, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("“Potential comebacks” are statistical resurgence candidates, not proof of real-world revival.")

elif page == "Trend Timeline":
    st.title("Trend Timeline")
    if not mapreduce_ready:
        need_mapreduce()
    params = sidebar_parameters()
    topics_df = cached_summary(1, 3000)
    topic = st.selectbox("Topic (sorted by total mentions)", topics_df["topic"].tolist())
    periods, counts = load_series(db, [topic], granularity)[topic]
    result = detect_comeback(counts, periods, params, topic)
    st.plotly_chart(timeline_figure(periods, counts, result, topic), use_container_width=True)
    if result["status"] == STATUS_COMEBACK:
        st.success(f"Detected resurgence pattern: **potential comeback** ({result['n_events']} event(s); metrics show the most recent).")
        m = st.columns(5)
        m[0].metric("Earlier peak", result["peak_count"], help=f"Period {result['peak_period']}")
        m[1].metric("Decline", f"{result['decline_percentage']:.0f}%")
        m[2].metric(f"Quiet period ({unit})", result["quiet_periods"])
        m[3].metric("Baseline / current", f"{result['baseline_count']:.1f} → {result['current_count']}")
        m[4].metric("Growth", f"{result['growth_percentage']:,.0f}%")
    else:
        st.info(f"Status with current thresholds: `{result['status']}`. Total mentions: {result['total_mentions']:,}.")

elif page == "Comeback Detector":
    st.title("Comeback Detector")
    if not mapreduce_ready:
        need_mapreduce()
    params = sidebar_parameters()
    cap = st.sidebar.number_input("Max topics to analyse (by mentions)", 100, 50000, 5000, step=500)
    results = cached_detection(params_to_dict(params), granularity, int(cap))
    table = results_table(results)
    found = table[table["status"] == STATUS_COMEBACK].drop(columns=["status"])
    st.write(f"Analysed **{len(table):,}** topics ({granularity} periods). "
             f"**{len(found):,}** labelled *potential comeback* (resurgence candidates).")
    if len(found) == 0:
        st.info("No candidates with these thresholds. Try a shorter quiet period or a lower growth threshold.")
    else:
        found = found.rename(columns={"peak_count": "earlier_peak", "quiet_periods": f"quiet_{unit}", "current_count": "current_mentions",
                                      "baseline_count": "baseline_mentions"})
        found["detection_status"] = "Potential comeback"
        st.dataframe(found.sort_values("growth_percentage", ascending=False).round(1), use_container_width=True, hide_index=True)
        st.download_button("Download CSV", found.to_csv(index=False), "comeback_candidates.csv", "text/csv")
    stored = get_metadata(db, "detection_run")
    if stored:
        st.caption(f"Last saved run (scripts/detect_comebacks.py): {stored['potential_comebacks']} candidates, {stored['ran_at']:%Y-%m-%d %H:%M} UTC.")

elif page == "Topic Comparison":
    st.title("Topic Comparison")
    if not mapreduce_ready:
        need_mapreduce()
    topics_df = cached_summary(1, 3000)
    chosen = st.multiselect("Select topics", topics_df["topic"].tolist(), default=topics_df["topic"].tolist()[:3])
    mode = st.radio("Scale", ["Raw mentions", "Share of each topic's own peak (0-100%)"], horizontal=True)
    if chosen:
        series = load_series(db, chosen, granularity)
        fig = go.Figure()
        for topic, (periods, counts) in series.items():
            y = counts if mode == "Raw mentions" else [c / max(counts) * 100 for c in counts]
            fig.add_trace(go.Scatter(x=periods, y=y, mode="lines", name=topic))
        fig.update_layout(template="plotly_white", height=480, xaxis_title=f"{granularity.capitalize()} start (UTC)",
                          yaxis_title="Mentions" if mode == "Raw mentions" else "% of own peak", legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"{LABEL[granularity].capitalize()} counts. Each topic is plotted from its first appearance; "
                   "topics that appeared later have shorter histories, so compare shapes (use the % view) with care.")
        st.dataframe(topics_df[topics_df["topic"].isin(chosen)][["topic", "total_mentions", "active_periods", "first_period", "last_period", "peak_count", "peak_period"]],
                     hide_index=True, use_container_width=True)
    else:
        st.info("Select at least one topic.")

else:
    st.title("Data & Methodology")
    st.subheader("Dataset")
    ds = ingest or {}
    st.write({"Name": ds.get("dataset_name") or "not configured (set DATASET_NAME in .env)",
              "Source": ds.get("dataset_source") or "not configured (set DATASET_SOURCE in .env)",
              "Licence": ds.get("dataset_license") or "not configured (set DATASET_LICENSE in .env)",
              "Columns": ds.get("columns"), "Rows processed at ingestion": ds.get("processed")})
    if prep:
        st.subheader("Cleaning summary")
        st.write({k: prep.get(k) for k in ("original_count", "duplicates", "missing_timestamp", "missing_text", "retained",
                                           "rejected_total", "final_usable_count", "topic_mode_used", "timezone", "date_start", "date_end")})
        st.write("Rejected by reason:", prep.get("rejected"))
    st.subheader("MapReduce execution")
    if mr:
        st.write({"Status": mr.get("status"), "Server version": mr.get("server_version"), "Granularity": mr.get("granularity"),
                  "Ran at": str(mr.get("ran_at")), "Jobs": mr.get("jobs"), "Independent validation": mr.get("validation")})
    else:
        st.warning("MapReduce has not been run.")
    st.subheader("Detection parameters (current defaults from detection_params.json)")
    st.json(params_to_dict(load_params(DETECTION_PARAMS_FILE)))
    st.subheader("Methodology")
    st.markdown("""
1. Posts are imported, cleaned (UTC timestamps, de-duplication) and mapped to **topics** (hashtags or keywords).
2. **MapReduce Job 1** (runs inside MongoDB) counts mentions per *(topic, period)*. **Job 2** summarises each topic.
3. A **rule-based algorithm** looks for: an earlier peak → a sustained decline → a quiet period → renewed attention that is
   large compared with the quiet baseline. Steady growth never produces a quiet period, so it is not flagged.
4. Results are called *potential comebacks* / *resurgence candidates*.
""")
    st.subheader("Limitations")
    st.markdown("""
- Topics are extracted by string matching, with no semantic understanding.
- Thresholds are practical defaults, not scientific constants; results change with them.
- The dataset is historical: nothing here describes current social media trends.
- The last period of the data may be incomplete, which can understate recent activity.
- A detected pattern shows renewed mentions in *this dataset only*, not real-world popularity.
""")
