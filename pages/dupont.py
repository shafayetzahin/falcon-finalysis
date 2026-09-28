"""DuPont visual decomposition and symmetric driver attribution."""
import streamlit as st
from core.dupont_engine import attribution
from components.ui import require_analysis, company_header, chart, table, assumptions
from components.formatting import fmt

a = require_analysis()
company_header('DuPont Analysis')
latest = a.dupont.iloc[-1]
st.metric('Return on equity', fmt(latest['DuPont ROE'], '%'), border=True)
st.caption('NET PROFIT MARGIN  ×  ASSET TURNOVER  ×  EQUITY MULTIPLIER  =  RETURN ON EQUITY')
cols = st.columns(3)
for col, name, unit in zip(cols, a.dupont.columns[:3], ['%', 'x', 'x']):
    col.metric(name, fmt(latest[name], unit), border=True)
effects = attribution(a.dupont)
st.subheader('What changed ROE?')
for name, effect in effects.items():
    st.write(f'**{name}**: ' + ('N/A' if effect != effect else f'{effect*100:+.2f} percentage points'))
if effects.notna().all():
    driver = effects.abs().idxmax()
    st.info(f'The largest absolute contribution came from {driver.lower()}. This arithmetic attribution suggests a driver of the change; it does not establish causation.')
st.caption('Attribution averages all six factor replacement orders so contributions sum exactly to the change in DuPont ROE.')
chart(a.dupont, ['DuPont ROE', 'Net Profit Margin'], 'Returns & profitability', '%')
chart(a.dupont, ['Asset Turnover', 'Equity Multiplier'], 'Efficiency & financial leverage', 'x')
table(a.dupont.T)
assumptions()
