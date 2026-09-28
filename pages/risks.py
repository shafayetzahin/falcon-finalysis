"""Strengths, risks and areas to investigate, grouped by severity."""
import streamlit as st
from core.config import GUIDELINE
from components.ui import require_analysis, company_header, signal_card

a = require_analysis()
company_header('Key Insights & Risk Flags')
st.caption('Deterministic signals grounded in the reported statements. ' + GUIDELINE)
tabs = st.tabs(['Strengths', 'Risks', 'Areas to monitor'])
for tab, severities in zip(tabs, [['POSITIVE'], ['HIGH RISK', 'WARNING'], ['WATCH', 'INFO']]):
    with tab:
        matching = [f for f in a.flags if f.severity in severities]
        if not matching:
            st.info('No available metric triggered a configured rule in this category. Review data coverage as well.')
        cols = st.columns(2)
        for i, flag in enumerate(matching):
            with cols[i % 2]:
                signal_card(flag)
with st.expander('Rule thresholds'):
    st.write('Current ratio < 1; quick ratio < 0.75; negative working capital; interest coverage < 2 (high risk below 1); negative margins or OCF; FCF negative in both latest years; net margin declines across three observations; working-capital days deteriorate by more than 5 days; debt/equity rises by more than 0.15x; liabilities grow over 10pp faster than assets or equity. Positive signals compare available consecutive observations. Multi-year rules require complete observations.')
