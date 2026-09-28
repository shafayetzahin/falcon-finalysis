"""Manual competitor comparison with explicit period/currency compatibility."""
import streamlit as st
import pandas as pd
from data.parsers import read_file, prepare
from components.ui import require_analysis, company_header, cached_analysis
from components.formatting import fmt, unit_for

a = require_analysis()
company_header('Peer Comparison')
st.caption('Upload up to 20 values-only competitor files using the same annual schema. Ratios are compared for a common fiscal year. Revenue levels are omitted because currencies and company scale can differ.')
uploads = st.file_uploader('Competitor statements', type=['csv', 'xlsx'], accept_multiple_files=True)
keys = ['Revenue Growth', 'Net Profit Margin', 'ROA', 'ROE', 'Current Ratio', 'Debt-to-Equity',
        'Interest Coverage', 'Asset Turnover', 'Cash Conversion Cycle']
year = st.selectbox('Comparison fiscal year', list(a.statements.index), index=len(a.statements)-1)
rows = {st.session_state.meta['company_name']: a.combined.loc[year, keys]}
if len(uploads) > 20:
    st.error('Select at most 20 competitors.')
    st.stop()
for i, upload in enumerate(uploads):
    try:
        peer = cached_analysis(prepare(read_file(upload.getvalue(), upload.name)), .01)
        if year not in peer.combined.index:
            st.warning(f'{upload.name}: no FY{year} data; excluded.')
            continue
        label = f'{upload.name.rsplit(".", 1)[0]} ({i+1})'
        rows[label] = peer.combined.loc[year, keys]
        if any(issue.severity == 'WARNING' for issue in peer.issues):
            st.warning(f'{upload.name}: reconciliation warnings exist. Review source figures before comparing.')
    except ValueError as exc:
        st.error(f'{upload.name}: {exc}')
comparison = pd.DataFrame(rows).T
formatted = comparison.astype(object)
for key in keys:
    formatted[key] = [fmt(v, unit_for(key)) for v in comparison[key]]
st.dataframe(formatted, width='stretch')
st.caption('Same year labels do not guarantee identical fiscal year-end dates or accounting policies. Compare business models and definitions before drawing conclusions. No composite peer ranking is applied.')
if len(comparison) > 1:
    subject = comparison.iloc[0]
    for name, row in comparison.iloc[1:].iterrows():
        if pd.notna(subject['Net Profit Margin']) and pd.notna(row['Net Profit Margin']) and pd.notna(subject['Debt-to-Equity']) and pd.notna(row['Debt-to-Equity']):
            profitability = 'higher' if subject['Net Profit Margin'] > row['Net Profit Margin'] else 'lower' if subject['Net Profit Margin'] < row['Net Profit Margin'] else 'equal'
            leverage = 'higher' if subject['Debt-to-Equity'] > row['Debt-to-Equity'] else 'lower' if subject['Debt-to-Equity'] < row['Debt-to-Equity'] else 'equal'
            st.write(f'Relative to {name}, the active company has {profitability} net margin and {leverage} debt-to-equity in FY{year}. These dimensions do not establish which business is objectively better.')
