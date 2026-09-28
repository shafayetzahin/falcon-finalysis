"""Dedicated review center for completeness, consistency and provenance."""
import pandas as pd
import streamlit as st

from components.ui import header
from core.data_quality import assess_financial_data


header("Data Quality Center", "Check completeness, continuity, accounting consistency and source traceability before analysis.")

if "frame" not in st.session_state:
    st.info("Load a company, import statements or use the demo to run a quality review.")
    st.page_link("pages/projects.py", label="Open Projects & Data →")
    st.stop()

report = assess_financial_data(
    st.session_state.frame, st.session_state.get("provenance"),
    st.session_state.get("tolerance", .01))

cols = st.columns(3)
cols[0].metric("Readiness score", f"{report.score:.0f} / 100")
cols[1].metric("Financial-field coverage", f"{report.coverage:.0%}")
cols[2].metric("Source traceability", f"{report.provenance_coverage:.0%}")
st.progress(report.score / 100)
st.caption("This score measures input readiness. It does not certify accuracy, audit status or investment quality.")

if report.issues.empty:
    st.success("No structural or reconciliation concern was detected in the available values.")
else:
    st.subheader("Review queue")
    filters = st.multiselect("Show severity", ["ERROR", "WARNING", "REVIEW"],
                             default=["ERROR", "WARNING", "REVIEW"])
    shown = report.issues[report.issues["Severity"].isin(filters)]
    st.dataframe(shown, hide_index=True, width="stretch")

st.subheader("Recommended next steps")
for number, step in enumerate(report.next_steps, 1):
    st.write(f"**{number}.** {step}")

coverage_tab, source_tab = st.tabs(["Field coverage", "Recorded sources"])
with coverage_tab:
    field_coverage = report.field_coverage.copy()
    field_coverage["Coverage"] = field_coverage["Coverage"].map(lambda value: f"{value:.0%}")
    st.dataframe(field_coverage, hide_index=True, width="stretch")
with source_tab:
    provenance = st.session_state.get("provenance")
    if isinstance(provenance, pd.DataFrame) and not provenance.empty:
        st.dataframe(provenance, hide_index=True, width="stretch")
    else:
        st.info("No value-level source references are recorded for this session.")

st.page_link("pages/projects.py", label="Correct data or source references →")
