"""Executive overview with transparent summary metrics and a demonstration entry path."""
import streamlit as st
import pandas as pd
from components.ui import require_analysis, header, metrics, chart, signal_card, assumptions

if 'frame' not in st.session_state:
    header('Financial analysis made easier.', 'Choose one starting point. Falcon Finalysis will guide you through review, analysis and export.')
    if st.button('Try a complete demo', type='primary'):
        st.session_state.open_demo_request = True
        st.rerun()
    st.markdown('### Choose your task')
    items = [
        ('Analyze a company', 'Start with a DSE/CSE ticker, collect public facts and review the available financial data.', 'pages/market.py'),
        ('Compare companies', 'Choose suggested industry peers or upload statements, then compare the same fiscal year.', 'pages/industry_comparison.py'),
        ('Manage a portfolio', 'Review stock prices, corporate actions, holdings, returns and risk.', 'pages/portfolio.py'),
    ]
    for start in range(0, len(items), 3):
        cols = st.columns(3)
        for col, (title, text, page) in zip(cols, items[start:start + 3]):
            with col, st.container(border=True):
                st.subheader(title)
                st.write(text)
                if page:
                    st.page_link(page, label='Open →')
    st.page_link('pages/projects.py', label='Upload PDF, Excel or CSV statements — or enter figures manually →')
    with st.expander('More analysis tools'):
        st.page_link('pages/data_quality.py', label='Check source coverage and data quality')
        st.page_link('pages/valuation.py', label='Build a valuation from reviewed statements')
        st.page_link('pages/credgrid.py', label='Review small-business credit with CredGrid')
    st.info('Start with the fictional demo to learn the workflow. For your own company, review the source values before using results and download a project recovery copy.')
    st.markdown('### What happens next')
    st.write('**Review data quality → understand ratios and trends → investigate risks → test a scenario → download PDF and Excel reports.**')
    st.stop()

a = require_analysis()
meta = st.session_state.meta
header(meta['company_name'], f'{meta.get("industry", "")} · {meta["currency"]} · FY{a.statements.index.min()}–FY{a.statements.index.max()} · {len(a.statements)} years · Updated {meta.get("updated_at", "unsaved session")}')
if st.session_state.get('demo_mode'):
    st.caption('PORTFOLIO DEMO · Fictional statements · Explore Overview → Key Insights → Financial Analysis → Scenario Lab → Generated Report')
score = a.health[-1]
left, right = st.columns([1, 3])
with left, st.container(border=True):
    st.caption('FALCON FINALYSIS FINANCIAL HEALTH SCORE')
    st.metric(score.label, 'N/A' if score.score is None else f'{score.score:.0f} / 100')
    st.progress((score.score or 0)/100)
    st.caption(f'{score.coverage:.0%} weighted data coverage · Generic analytical model')
    st.page_link('pages/health.py', label='How this score works →')
with right:
    st.subheader('Performance at a glance')
    metrics(a.combined, ['Revenue', 'Net Income', 'ROE', 'Operating Cash Flow'], 2)
    st.caption('Changes compare the latest two years. pp = percentage points. Currency values use K, M and B scales.')
if any(i.severity == 'WARNING' for i in a.issues):
    st.warning('DATA QUALITY WARNING · Reconciliation differences exist. Review Projects & Data before relying on the analysis.')
chart(a.combined, ['Revenue', 'Net Income', 'Operating Cash Flow'], 'Revenue, profit & cash generation', 'millions')
st.subheader('Financial dimensions')
cols = st.columns(6)
for col, (_, row) in zip(cols, score.categories.iterrows()):
    with col:
        st.caption(row['Category'])
        st.write('N/A' if pd.isna(row['Score / 100']) else f'{row["Score / 100"]:.0f} / 100')
        st.progress(0 if pd.isna(row['Score / 100']) else row['Score / 100']/100)
st.divider()
metrics(a.combined, ['Revenue Growth', 'Gross Profit Margin', 'Operating Margin', 'Net Profit Margin',
                     'ROA', 'Current Ratio', 'Debt-to-Equity', 'Interest Coverage', 'Free Cash Flow'], 3)
st.subheader('Key insights')
cols = st.columns(2)
chosen = [f for f in a.flags if f.severity == 'POSITIVE'][:2] + [f for f in a.flags if f.severity != 'POSITIVE'][:2]
for i, flag in enumerate(chosen):
    with cols[i % 2]:
        signal_card(flag)
with st.expander('Executive summary'):
    for title, prose in a.summary.items():
        st.markdown('**' + title + '**')
        st.write(prose)
history = pd.DataFrame({'Health score': [h.score for h in a.health]}, index=a.statements.index)
chart(history, ['Health score'], 'Financial health over time', 'points')
assumptions()
