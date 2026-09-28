"""Cash cycle components and operating funding implications."""
import streamlit as st
from components.ui import require_analysis, company_header, metrics, chart, table, signal_card, assumptions

a = require_analysis()
company_header('Working Capital')
st.caption('Inventory → Receivables → Cash, offset by the supplier payment period')
metrics(a.combined, ['Inventory Days', 'Receivable Days', 'Payable Days', 'Cash Conversion Cycle'])
metrics(a.combined, ['Net Working Capital', 'Current Ratio'], 2)
chart(a.ratios, ['Inventory Days', 'Receivable Days', 'Payable Days', 'Cash Conversion Cycle'], 'Cash conversion cycle', 'days')
table(a.ratios[['Net Working Capital', 'Current Ratio', 'Inventory Days', 'Receivable Days', 'Payable Days', 'Cash Conversion Cycle']].T)
for flag in a.flags:
    if flag.metric in ['Cash Conversion Cycle', 'Receivable Days', 'Inventory Days', 'Payable Days']:
        signal_card(flag)
assumptions()
