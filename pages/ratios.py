"""Ratio registry with formulas, trend, status and interpretations."""
import streamlit as st
import pandas as pd
from dataclasses import asdict
from core.ratio_engine import METRICS, BY_NAME
from core.interpretation_engine import interpret
from core.config import GUIDELINE
from components.ui import require_analysis, company_header, chart, assumptions
from components.formatting import fmt

a = require_analysis()
company_header('Ratio Analysis')
category = st.selectbox('Financial dimension', list(dict.fromkeys(m.category for m in METRICS)))
names = [m.name for m in METRICS if m.category == category]
formatted = a.ratios[names].T.copy().astype(object)
for name in names:
    formatted.loc[name] = [fmt(v, BY_NAME[name].unit, st.session_state.meta['currency']) for v in a.ratios[name]]
st.dataframe(formatted, width='stretch')
metric = st.selectbox('Inspect a metric', names)
result = interpret(metric, a.combined, a.reasons[metric].iloc[-1])
st.subheader(result.status)
st.write(result.interpretation)
chart(a.ratios, [metric], metric + ' over time', '%' if BY_NAME[metric].unit == '%' else BY_NAME[metric].unit)
with st.expander('How is this calculated?', expanded=True):
    st.code(BY_NAME[metric].formula, language=None)
    st.caption(GUIDELINE)
    for year in a.reasons.index:
        if a.reasons.loc[year, metric]:
            st.write(f'FY{year}: {a.reasons.loc[year, metric]}')
with st.expander('Interpretations for this dimension'):
    rows = [asdict(interpret(name, a.combined, a.reasons[name].iloc[-1])) for name in names]
    st.dataframe(pd.DataFrame(rows)[['metric_name', 'trend', 'status', 'interpretation']], hide_index=True, width='stretch')
assumptions()
