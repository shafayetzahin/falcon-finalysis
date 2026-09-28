"""Operating, investing, financing and free cash flow."""
import streamlit as st
from components.ui import require_analysis, company_header, metrics, chart, table, signal_card, assumptions

a = require_analysis()
company_header('Cash Flow Analysis')
metrics(a.combined, ['Operating Cash Flow', 'Free Cash Flow', 'Operating Cash Flow Margin', 'Cash Flow to Net Income'])
chart(a.combined, ['Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow'], 'Sources & uses of cash', 'millions')
chart(a.combined, ['Operating Cash Flow', 'Net Income', 'Free Cash Flow'], 'Earnings-to-cash conversion', 'millions')
table(a.combined[['Operating Cash Flow', 'Capital Expenditure', 'Free Cash Flow', 'Capex Intensity', 'Cash Flow to Net Income']].T)
st.caption('FCF = operating cash flow − positive capital expenditure. Cash flow to net income is unavailable for nonpositive net income.')
for flag in a.flags:
    if flag.metric in ['Operating Cash Flow', 'Free Cash Flow']:
        signal_card(flag)
assumptions()
