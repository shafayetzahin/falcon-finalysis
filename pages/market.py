"""Beginner-friendly DSE/CSE company lookup and historical-price workspace."""
from datetime import date, timedelta, datetime, timezone
import streamlit as st
import pandas as pd

from components.ui import header
from core.config import FIELDS
from data.database import stamp
from data.provenance import provenance_for_frame
from data.market_data import (company_snapshot, exchange_financials, price_history,
                              read_price_file, ticker_catalog, bundled_ticker_catalog)
from reports.excel_report import exchange_input_template, market_data_workbook


header('Listed Company Data', 'Look up a DSE or CSE company, collect a chosen price period and export a ready-to-use Excel workbook.')
st.page_link('pages/industry_comparison.py', label='Compare this company with same-industry peers →')

with st.expander('How to use this page', expanded=True):
    st.markdown('''
1. Choose **DSE** or **CSE**, then type to filter ticker suggestions or enter one manually.
2. Load company details to confirm the company and see source-provided facts.
3. Choose a date range, fetch trading history and review the chart/table.
4. Download a prefilled financial template and complete missing statement fields from annual reports.
5. Download the managed price-history workbook when you need market data for further work.
''')
    st.caption('Market prices and company facts come from public exchange pages. Falcon Finalysis does not estimate missing exchange values.')


@st.cache_data(ttl=3600, show_spinner=False)
def cached_tickers(exchange: str):
    return ticker_catalog(exchange)


@st.cache_data(ttl=900, show_spinner=False)
def cached_snapshot(exchange: str, ticker: str):
    return company_snapshot(exchange, ticker)


@st.cache_data(ttl=900, show_spinner=False)
def cached_history(exchange: str, ticker: str, start: date, end: date):
    return price_history(exchange, ticker, start, end)


@st.cache_data(ttl=900, show_spinner=False)
def cached_financials(exchange: str, ticker: str):
    return exchange_financials(exchange, ticker)


def start_project(company, frame: pd.DataFrame) -> None:
    st.session_state.meta = {'company_name': company.company_name,
                             'industry': company.fields.get('Sector', ''),
                             'country': 'Bangladesh', 'currency': 'BDT',
                             'description': f'{exchange} listed company · ticker {ticker}', 'updated_at': stamp()}
    st.session_state.frame = frame
    st.session_state.provenance = provenance_for_frame(
        frame, f'{exchange} exchange', company.source_url)
    st.session_state.project_name = f'{ticker} financial analysis'
    st.session_state.project_id = None
    st.session_state.pop('scenario', None)
    st.switch_page('pages/projects.py')


c1, c2 = st.columns([1, 2])
exchange = c1.selectbox('Exchange', ['DSE', 'CSE'], key='market_exchange')
options_key = f'ticker_options_{exchange}'
if options_key not in st.session_state:
    st.session_state[options_key] = bundled_ticker_catalog(exchange)
if isinstance(st.session_state[options_key], list):
    st.session_state[options_key] = {value: '' for value in st.session_state[options_key]}
current_ticker = st.session_state.get(f'last_ticker_{exchange}', 'SQURPHARMA')
options = [current_ticker] + [value for value in st.session_state[options_key] if value != current_ticker]
catalog = st.session_state[options_key]
selected_ticker = c2.selectbox(
    'Company ticker', options, index=0, key=f'market_ticker_picker_{exchange}',
    placeholder='Type a ticker or choose a suggestion', accept_new_options=True,
    filter_mode='fuzzy', format_func=lambda value: f'{value} — {catalog[value]}' if catalog.get(value) else value,
    help='Search by ticker or company name. Press Enter to use a ticker that is not listed.')
ticker = str(selected_ticker or '').strip().upper()
st.session_state[f'last_ticker_{exchange}'] = ticker
st.session_state.market_ticker = ticker
suggestion_count = len(st.session_state[options_key])
st.caption(f'{suggestion_count:,} {exchange} ticker suggestions available. Type to filter, select a match, or press Enter to use your own ticker.')
if ticker and ticker not in catalog:
    st.info(f'Using manually entered ticker **{ticker}**. Falcon Finalysis will validate it when company details are loaded.')

snapshot_state = st.session_state.get('company_snapshot')
annual_key = st.session_state.get('exchange_financials_key')
setup_step = 3 if annual_key == (exchange, ticker) else 2 if (
    snapshot_state and snapshot_state.exchange == exchange and snapshot_state.ticker == ticker) else 1
st.progress(setup_step / 3, text=f'Guided setup · step {setup_step} of 3')
st.markdown('**Step 1 · Select and confirm the company**')

list_col, detail_col = st.columns(2)
if list_col.button('Refresh ticker suggestions', width='stretch'):
    try:
        current_catalog = st.session_state[options_key]
        refreshed_catalog = cached_tickers(exchange)
        st.session_state[options_key] = {
            ticker: name or current_catalog.get(ticker, '')
            for ticker, name in refreshed_catalog.items()
        }
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))

if detail_col.button('Load company details', type='primary', width='stretch', disabled=not ticker):
    try:
        st.session_state.company_snapshot = cached_snapshot(exchange, ticker)
    except ValueError as exc:
        st.error(str(exc))

snapshot = st.session_state.get('company_snapshot')
if snapshot and snapshot.exchange == exchange and snapshot.ticker == ticker:
    st.success('Company confirmed. Continue to Step 2 to collect available annual exchange figures.')
    st.subheader(snapshot.company_name)
    st.caption(f'{snapshot.exchange}: {snapshot.ticker} · fetched {snapshot.fetched_at} · official source')
    details = pd.DataFrame(snapshot.fields.items(), columns=['Company detail', 'Value'])
    st.dataframe(details, hide_index=True, width='stretch', height=min(500, 36 * (len(details) + 1)))
    st.link_button(f'Open on {exchange}', snapshot.source_url)
    if st.button('Start with a blank financial template'):
        year = date.today().year
        start_project(snapshot, pd.DataFrame({'Year': range(year - 4, year + 1)}).reindex(columns=['Year'] + FIELDS))

    st.subheader('Step 2 · Prefill the financial template')
    st.write('The exchanges publish a small annual summary. Falcon Finalysis copies only directly reported values, then leaves the remaining statement fields blank for you to complete from annual reports.')
    if st.button('Load available annual figures from the exchange'):
        try:
            st.session_state.exchange_financials = cached_financials(exchange, ticker)
            st.session_state.exchange_financials_key = (exchange, ticker)
        except ValueError as exc:
            st.error(str(exc))
    annual = st.session_state.get('exchange_financials')
    if annual is not None and st.session_state.get('exchange_financials_key') == (exchange, ticker):
        st.success(f'Found {len(annual.details)} directly reported annual data points across {annual.frame.Year.nunique()} years.')
        st.dataframe(annual.details, hide_index=True, width='stretch')
        template = exchange_input_template(annual.frame, annual.details, exchange, ticker,
                                           annual.source_url, annual.fetched_at)
        st.subheader('Step 3 · Download or start the analysis')
        template_col, project_col = st.columns(2)
        template_col.download_button('Download prefilled analysis template', template,
                                     f'Falcon_Finalysis_{exchange}_{ticker}_template.xlsx',
                                     mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                     width='stretch', type='primary')
        if project_col.button('Use available values in a new project', width='stretch'):
            start_project(snapshot, annual.frame)
        st.info('Net Income is copied into the canonical Financial Data sheet when available. EPS, NAV per share, dividends and yield stay on Exchange Data because the core model needs their matching share and cash-dividend inputs.')
        st.caption('After completing missing statement fields in Projects & Data, open Valuation Lab for WACC, ROIC, DCF sensitivity and comparable-company ranges.')
        st.page_link('pages/valuation.py', label='Open Valuation Lab →')

st.divider()
st.subheader('Historical price period')
today = date.today()
d1, d2 = st.columns(2)
start = d1.date_input('From', today - timedelta(days=90), max_value=today, format='DD/MM/YYYY')
end = d2.date_input('To', today, max_value=today, format='DD/MM/YYYY')
if st.button('Fetch official price history', type='primary'):
    try:
        history, source = cached_history(exchange, ticker, start, end)
        st.session_state.market_history = history
        st.session_state.market_source = source
        st.session_state.market_fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        st.session_state.market_history_key = (exchange, ticker)
    except ValueError as exc:
        st.error(str(exc))

with st.expander('Exchange download fallback'):
    st.write('If the exchange blocks live access, download its historical table as CSV/XLSX and upload it here. Required columns: Date, Close and Volume.')
    uploaded = st.file_uploader('Price-history file', type=['csv', 'xlsx'], key='market_file')
    if uploaded and st.button('Use uploaded price history'):
        try:
            st.session_state.market_history = read_price_file(uploaded.getvalue(), uploaded.name, ticker)
            st.session_state.market_source = f'User upload: {uploaded.name}'
            st.session_state.market_fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            st.session_state.market_history_key = (exchange, ticker)
        except ValueError as exc:
            st.error(str(exc))

history = st.session_state.get('market_history')
if (isinstance(history, pd.DataFrame) and not history.empty
        and st.session_state.get('market_history_key') == (exchange, ticker)):
    shown = history.copy().sort_values('Date')
    fetched_text = st.session_state.get('market_fetched_at', '')
    try:
        fetched_time = datetime.fromisoformat(fetched_text.replace('Z', '+00:00'))
        age_minutes = max(0, int((datetime.now(timezone.utc) - fetched_time).total_seconds() / 60))
        freshness = 'Fresh' if age_minutes <= 15 else 'Review freshness'
        fetched_display = fetched_time.strftime('%d/%m/%Y %H:%M UTC')
    except (ValueError, TypeError):
        age_minutes, freshness = None, 'Unknown'
        fetched_display = 'time unavailable'
    unique_dates = shown['Date'].nunique()
    duplicate_rows = int(len(shown) - unique_dates)
    missing_close = int(pd.to_numeric(shown['Close'], errors='coerce').isna().sum())
    st.line_chart(shown.set_index('Date')['Close'], y_label='Close price (BDT)')
    latest = shown.iloc[-1]
    cols = st.columns(4)
    cols[0].metric('Latest close', f'{latest.Close:,.2f} BDT')
    cols[1].metric('Trading records', f'{len(shown):,}')
    cols[2].metric('Total volume', f'{shown.Volume.sum():,.0f}')
    cols[3].metric('Data freshness', freshness,
                   'Just fetched' if age_minutes is not None and age_minutes == 0 else
                   (f'{age_minutes} minutes old' if age_minutes is not None else 'No timestamp'))
    market_source = st.session_state.get('market_source', 'Not recorded')
    st.caption(f"Source: {market_source} · retrieved {fetched_display}")
    unavailable_days = (shown['Date'].min().date() - start).days
    if ('dse.com.bd/company/' in market_source and unavailable_days > 7):
        st.warning(f"DSE's current public company page supplied records from {shown['Date'].min():%d/%m/%Y}. "
                   'Earlier dates in the selected period were unavailable from that page; use the exchange download fallback if needed.')
    if duplicate_rows or missing_close:
        st.warning(f'Data review: {duplicate_rows} duplicate date row(s) and {missing_close} missing close value(s).')
    else:
        st.success('Basic market-data checks passed: unique trading dates and complete closing prices.')
    display_history = shown.sort_values('Date', ascending=False).copy()
    display_history['Date'] = display_history['Date'].dt.strftime('%d/%m/%Y')
    st.dataframe(display_history, hide_index=True, width='stretch')
    try:
        workbook = market_data_workbook(shown, exchange, ticker,
                                        st.session_state.get('market_source', ''),
                                        st.session_state.get('market_fetched_at', ''))
        st.download_button('Download managed Excel workbook', workbook,
                           f'{exchange}_{ticker}_{shown.Date.min():%Y%m%d}_{shown.Date.max():%Y%m%d}.xlsx',
                           mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', type='primary')
        st.caption('Workbook: Summary with chart, typed Price History, Monthly Summary, and source/refresh notes.')
    except ValueError as exc:
        st.error(str(exc))

st.caption('Exchange websites can change without notice. Always verify material figures on the linked official page. Market data is separate from audited financial statements and does not by itself produce company health ratios.')
