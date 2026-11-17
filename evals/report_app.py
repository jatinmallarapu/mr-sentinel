"""Inspect saved runs without exposing raw diffs to the dashboard."""

import json

import streamlit as st
from gap_analysis import buckets

st.title("MR Sentinel evaluation")
runs = st.file_uploader("Evaluation JSON reports", type="json", accept_multiple_files=True)
summaries = []
for upload in runs:
    report = json.load(upload)
    summaries.append(
        {
            key: report[key]
            for key in (
                "model",
                "engine",
                "examples",
                "precision",
                "recall",
                "f1",
                "p95_ms",
                "degraded",
            )
        }
    )
    with st.expander(upload.name):
        st.json(report["confusion"])
        st.table(
            [
                {"category": cat, "type": kind, "count": count}
                for (cat, kind), count in buckets(report).most_common()
            ]
        )
        st.table([row for row in report["cases"] if row["predicted"] is not row["label"]][:3])
if summaries:
    st.table(summaries)
