"""Download shared-analysis PDF and XLSX snapshots."""
import hashlib
import json
import streamlit as st
from reports.pdf_report import pdf_report
from reports.excel_report import excel_report
from components.ui import require_analysis, company_header, repository
from core.config import DISCLAIMER

a = require_analysis()
company_header('Generated Report')
st.write('Create an executive report or an Excel analysis workbook from the active company and Scenario Lab assumptions.')
st.caption('Reports include original statements, ratios, DuPont, working capital, growth, insights, methodology and scenario assumptions. Excel exports are values-only snapshots; recalculate in Falcon Finalysis after input changes.')
provenance = st.session_state.get('provenance')
provenance_json = provenance.to_json() if hasattr(provenance, 'to_json') else ''
fingerprint = hashlib.sha256((st.session_state.frame.to_json()+provenance_json+json.dumps(st.session_state.meta, sort_keys=True)+json.dumps(st.session_state.get('scenario'), sort_keys=True)+str(st.session_state.get('tolerance', .01))).encode()).hexdigest()
if st.session_state.get('report_fingerprint') != fingerprint:
    st.session_state.pop('pdf_bytes', None)
    st.session_state.pop('xlsx_bytes', None)
if st.button('Generate PDF & Excel reports', type='primary'):
    with st.spinner('Preparing reports…'):
        st.session_state.pdf_bytes = pdf_report(a, st.session_state.meta, st.session_state.get('scenario'), provenance)
        st.session_state.xlsx_bytes = excel_report(a, st.session_state.meta, st.session_state.get('scenario'), provenance)
        st.session_state.report_fingerprint = fingerprint
        if st.session_state.get('project_id'):
            repository().log_report(st.session_state.project_id, 'PDF + XLSX generated')
    st.success('Reports are ready to download.')
if 'pdf_bytes' in st.session_state:
    cols = st.columns(2)
    cols[0].download_button('Download PDF analysis', st.session_state.pdf_bytes, 'Falcon_Finalysis_analysis.pdf', 'application/pdf', width='stretch')
    cols[1].download_button('Download Excel analysis', st.session_state.xlsx_bytes, 'Falcon_Finalysis_analysis.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', width='stretch')
st.subheader('Executive summary preview')
for heading, paragraph in a.summary.items():
    with st.expander(heading, expanded=heading == 'Financial Overview'):
        st.write(paragraph)
st.caption(DISCLAIMER)
