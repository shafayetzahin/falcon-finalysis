"""Growth rates, CAGR and multi-year direction."""
import streamlit as st
from components.ui import require_analysis, company_header, table, chart, assumptions

a = require_analysis()
company_header('Trend Analysis')
metric = st.selectbox('Metric', list(a.growth.columns))
chart(a.combined, [metric], metric + ' trend', 'millions' if metric != 'EPS' else 'currency / share')
st.subheader('Year-on-year growth')
table(a.growth.T, True)
st.subheader('Compound annual growth')
table(a.cagr.to_frame('CAGR'), True)
st.caption('CAGR requires at least three observations and positive endpoints, using elapsed fiscal years. Conventional YoY growth requires a positive prior base.')
st.subheader('Multi-year assessment')
st.dataframe(a.trends.style.format({'Current': '{:,.2f}', 'Previous': '{:,.2f}', 'YoY change': '{:.1%}', 'Volatility': '{:.1%}'}, na_rep='N/A'), width='stretch')
st.caption('Direction requires three observations and two consistent movements; mixed paths are shown as Mixed trend. Volatility is population standard deviation / absolute mean over the latest three observations. Direction labels use relative change, not an industry benchmark. Higher is not always economically better; evaluate each metric in context.')
assumptions()
