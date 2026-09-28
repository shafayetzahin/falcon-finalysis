"""Auditable score methodology and weighted coverage."""
import streamlit as st
import pandas as pd
from core.health_score import POLICY
from core.config import GUIDELINE
from components.ui import require_analysis, company_header

a = require_analysis()
company_header('Financial Health Score Methodology')
h = a.health[-1]
st.metric('Falcon Finalysis Financial Health Score', 'N/A' if h.score is None else f'{h.score:.1f} / 100', border=True)
st.write(h.label + f' · {h.coverage:.0%} weighted data coverage')
st.warning('This is a Falcon Finalysis analytical model, not an industry-standard credit score. ' + GUIDELINE)
st.dataframe(h.categories.style.format({'Score / 100': '{:.1f}', 'Coverage': '{:.0%}', 'Points earned': '{:.2f}', 'Available points': '{:.1f}'}, na_rep='N/A'), hide_index=True, width='stretch')
rows = []
for category, (weight, rules) in POLICY.items():
    for metric, low, high, inverse in rules:
        rows.append({'Category': category, 'Metric': metric, 'Category points': weight,
                     '0-score threshold': high if inverse else low, '100-score threshold': low if inverse else high})
st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
st.write('Each category splits its weight equally across its metrics. Scores interpolate linearly between thresholds and are clipped to 0–100. Decimal ratios are used (0.15 means 15%). Revenue Stability is the standard deviation of the latest two annual revenue growth rates; lower values score higher.')
st.write('Missing inputs reduce weighted coverage. Overall score is withheld below 75% coverage or when any category has no evidence. Otherwise it is normalized over available weights. Partial coverage can change comparisons across years; review the coverage alongside the score.')
st.write('85–100 Strong · 70–<85 Healthy · 55–<70 Moderate · 40–<55 Weak · 0–<40 High Financial Risk')
st.caption('Limitations: generic thresholds; accounting policies and business models differ; negative equity and losses can make conventional ratios unavailable; quality warnings are not encoded as automatic score penalties; scoring is not predictive.')
