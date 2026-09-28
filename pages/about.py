"""Project purpose, skills and practical boundaries."""
from pathlib import Path
import streamlit as st
from core.config import DISCLAIMER
from components.ui import header

header('About Falcon Finalysis', 'Financial analysis meets software engineering.')
st.write('Falcon Finalysis was built to bridge financial analysis and technology by transforming raw accounting data into structured financial insight and decision-support analytics.')
st.subheader('Logo concepts')
st.caption('Concept C is the active identity. Concepts A and B remain here for future comparison.')
asset_dir = Path(__file__).resolve().parents[1] / 'assets' / 'logo-concepts'
logo_cols = st.columns(3)
for col, label, filename, description in zip(
        logo_cols,
        ['A · Falcon + chart', 'B · Data wing', 'C · Premium monogram'],
        ['concept-a-falcon-chart.png', 'concept-b-data-wing.png', 'concept-c-premium-monogram.png'],
        ['Direct and energetic', 'Clean and analytical', 'Premium and restrained']):
    with col, st.container(border=True):
        st.image(str(asset_dir / filename), width='stretch')
        selected = filename == 'concept-c-premium-monogram.png'
        st.markdown(f'**{label}**' + (' · **SELECTED**' if selected else ''))
        st.caption(description + (' · Current Falcon Finalysis identity' if selected else ''))
cols = st.columns(3)
for i, (name, description) in enumerate([
    ('Finance', 'Statement analysis, DuPont decomposition, working capital and cash flow.'),
    ('Data analytics', 'Schema normalization, data quality checks and multi-year trend analysis.'),
    ('Financial modelling', 'Explicit assumptions, operating scenarios and sensitivity analysis.'),
    ('Software development', 'Modular Python, Streamlit, local SQLite storage and automated tests.'),
    ('Visualization', 'Interactive Plotly charts and executive dashboards.'),
    ('Automation', 'Deterministic interpretations and PDF / Excel reporting.')]):
    with cols[i % 3], st.container(border=True):
        st.subheader(name)
        st.write(description)
st.subheader('Local by design')
st.write('In the local edition, uploaded statements, calculations, saved projects and reports remain on your device. In the public hosted profile, saved work is isolated to a temporary browser session and may be removed when that session or server restarts. Optional DSE/CSE lookup sends only the selected ticker and date range to the exchange website. No external AI service is used for financial analysis. Streamlit usage telemetry is disabled.')
st.subheader('Future direction')
st.write('Industry benchmark profiles, a fully linked forecasting model, OCR for scanned reports and audited methodology extensions can build on the calculation interfaces. CredGrid now includes an uncalibrated, human-controlled cash-flow scorecard pilot; predictive credit validation, identity and bureau checks, production security and cloud multi-user access remain future work.')
st.caption(DISCLAIMER)
