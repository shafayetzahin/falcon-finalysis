"""Reported, horizontal and common-size financial statements."""
import streamlit as st
from core.config import INCOME, BALANCE, CASH_FLOW
from core.trend_engine import horizontal
from components.ui import require_analysis, company_header, table, chart, assumptions

a = require_analysis()
company_header('Financial Statements')
st.caption('Reported amounts in full ' + st.session_state.meta['currency'] + ' units. Figures are not automatically repaired or derived.')
for tab, columns in zip(st.tabs(['Income statement', 'Balance sheet', 'Cash flow']), [INCOME, BALANCE, CASH_FLOW]):
    with tab:
        table(a.statements[columns].T)
st.subheader('Horizontal analysis')
base = st.selectbox('Base year', list(a.statements.index))
h = horizontal(a.statements, base)
items = st.multiselect('Statement items', list(a.statements.columns), default=['Revenue', 'Net Income', 'Total Assets'])
st.dataframe(h[h.Metric.isin(items)].style.format({'Value': '{:,.2f}', 'Absolute change': '{:+,.2f}', 'Percentage change': '{:+.1%}'}, na_rep='N/A'), hide_index=True, width='stretch')
st.subheader('Common-size analysis')
tabs = st.tabs(['Income / revenue', 'Balance sheet / assets'])
with tabs[0]:
    table(a.vertical[INCOME].T, True)
    chart(a.vertical, ['COGS', 'Operating Expenses', 'Net Income'], 'Income statement composition', '%')
with tabs[1]:
    table(a.vertical[BALANCE].T, True)
    chart(a.vertical, ['Total Liabilities', 'Shareholders Equity'], 'Capital structure', '%')
assumptions()
