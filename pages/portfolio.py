"""Multi-stock return, corporate-action and portfolio-risk workspace."""
from datetime import date, timedelta, datetime, timezone
from html import escape
import json

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from components.ui import header, repository
from core.portfolio_engine import (ACTION_COLUMNS, HOLDING_COLUMNS, analyze_portfolio,
                                   efficient_frontier, portfolio_risk_contribution,
                                   rebalance_plan)
from data.market_data import (bundled_ticker_catalog, exchange_financials,
                              price_history, read_price_file)


header('Portfolio Management',
       'Compare selected DSE/CSE stocks, include corporate actions and measure return and risk.')
st.warning('Decision support only. A qualified human must verify the source data, approve the recommendation and confirm every final investment procedure.')

with st.expander('How the calculations work', expanded=True):
    st.markdown('''
1. Select stocks and a common price period, then fetch or upload closing-price history.
2. Review exchange dividend references and enter dated corporate actions that occurred inside the period.
3. Set portfolio weights and choose daily, weekly or monthly return observations.
4. Calculate holding-period return, average return, standard deviation, variance and covariance.
''')
    st.caption('For Bangladesh declarations, cash dividend % is normally based on face value. Enter face value as well, or enter the exact BDT cash dividend per share. Corporate-action dates and terms must be verified against the issuer/exchange notice.')


@st.cache_data(ttl=900, show_spinner=False)
def cached_history(exchange: str, ticker: str, start: date, end: date):
    return price_history(exchange, ticker, start, end)


@st.cache_data(ttl=900, show_spinner=False)
def cached_dividend_reference(exchange: str, ticker: str):
    return exchange_financials(exchange, ticker)


def frame_records(frame: pd.DataFrame) -> list[dict]:
    """Return JSON-safe records, preserving dates and replacing NaN with null."""
    return json.loads(frame.to_json(orient='records', date_format='iso'))


def portfolio_payload(histories: dict[str, pd.DataFrame], actions: pd.DataFrame,
                      holdings: pd.DataFrame, weights: pd.DataFrame,
                      exchange: str, frequency: str, risk_free_rate: float) -> dict:
    return {
        'exchange': exchange, 'frequency': frequency, 'risk_free_rate': risk_free_rate,
        'histories': {ticker: frame_records(frame) for ticker, frame in histories.items()},
        'actions': frame_records(actions), 'holdings': frame_records(holdings),
        'weights': frame_records(weights),
        'sources': st.session_state.get('portfolio_sources', {}),
        'fetched_at': st.session_state.get('portfolio_fetched_at', ''),
    }


def restore_portfolio(meta: dict, payload: dict) -> None:
    histories = {ticker: pd.DataFrame(records) for ticker, records in payload['histories'].items()}
    for frame in histories.values():
        frame['Date'] = pd.to_datetime(frame['Date'])
    actions = pd.DataFrame(payload.get('actions', [])).reindex(columns=ACTION_COLUMNS)
    if not actions.empty:
        actions['Date'] = pd.to_datetime(actions['Date'], errors='coerce')
    st.session_state.portfolio_histories = histories
    st.session_state.portfolio_actions = actions
    st.session_state.portfolio_holdings = pd.DataFrame(payload.get('holdings', [])).reindex(columns=HOLDING_COLUMNS)
    st.session_state.portfolio_weights = pd.DataFrame(payload.get('weights', []))
    st.session_state.portfolio_sources = payload.get('sources', {})
    st.session_state.portfolio_fetched_at = payload.get('fetched_at', '')
    st.session_state.portfolio_saved_id = meta['id']
    st.session_state.portfolio_name = meta['name']
    st.session_state.portfolio_exchange = payload.get('exchange', 'DSE')
    st.session_state.portfolio_frequency = payload.get('frequency', 'Monthly')
    st.session_state.portfolio_risk_free = float(payload.get('risk_free_rate', 0)) * 100
    st.session_state.pop('portfolio_analysis', None)


def portfolio_report_html(name: str, analysis, sources: dict[str, str], frequency: str) -> bytes:
    summary = analysis.portfolio_summary
    metrics = ''.join(
        f'<li><strong>{escape(label)}:</strong> {value}</li>' for label, value in [
            ('Annualized average return', f'{summary["Annualized Average Return"]:.2%}'),
            ('Annualized volatility', f'{summary["Annualized Volatility"]:.2%}'),
            ('Sharpe ratio', f'{summary["Sharpe Ratio"]:.2f}'),
            ('Sortino ratio', f'{summary["Sortino Ratio"]:.2f}'),
            ('Maximum drawdown', f'{summary["Maximum Drawdown"]:.2%}'),
            ('Historical VaR (95%, one period)', f'{summary["Historical VaR 95%"]:.2%}'),
        ])
    source_rows = ''.join(f'<tr><td>{escape(ticker)}</td><td>{escape(str(source))}</td></tr>'
                          for ticker, source in sources.items())
    html = f'''<!doctype html><html><head><meta charset="utf-8"><title>{escape(name)}</title>
<style>body{{font:15px Arial;max-width:1100px;margin:40px auto;color:#17324d}}h1,h2{{color:#073b4c}}
table{{border-collapse:collapse;width:100%;margin:12px 0 28px}}th,td{{border:1px solid #ccd7df;padding:7px;text-align:right}}
th{{background:#e9f5f4}}td:first-child,th:first-child{{text-align:left}}.notice{{background:#fff3cd;padding:14px;border-left:5px solid #c68a00}}</style></head><body>
<h1>Falcon Finalysis — {escape(name)}</h1><p>Return frequency: {escape(frequency)}</p>
<div class="notice"><strong>Decision support only.</strong> A qualified human must verify the data and approve the final procedure.</div>
<h2>Portfolio summary</h2><ul>{metrics}</ul><h2>Holding-period results</h2>
{analysis.asset_summary.to_html(index=False, border=0, float_format=lambda value: f'{value:,.4f}')}
<h2>Risk statistics</h2>{analysis.risk_summary.to_html(index=False, border=0, float_format=lambda value: f'{value:,.6f}')}
<h2>Covariance</h2>{analysis.covariance.to_html(border=0, float_format=lambda value: f'{value:,.6f}')}
<h2>Sources</h2><table><tr><th>Ticker</th><th>Source</th></tr>{source_rows}</table>
<p>Calculations exclude taxes and dividend reinvestment. Transaction fees are included only where entered. Risk measures use aligned observations.</p>
</body></html>'''
    return html.encode('utf-8')


def demo_portfolio() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Return deterministic fictional prices and actions for an offline guided example."""
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=160)
    step = np.arange(len(dates), dtype=float)
    prices = {
        'FALCON-A': 80 * np.exp(.0008 * step + .025 * np.sin(step / 9)),
        'FALCON-B': 55 * np.exp(.0003 * step + .04 * np.sin(step / 13 + 1)),
        'FALCON-C': 105 * np.exp(-.0001 * step + .018 * np.sin(step / 7 + 2)),
    }
    prices['FALCON-A'][55:] -= 1.50
    prices['FALCON-B'][80:] /= 1.05
    rights_factor = (10 * prices['FALCON-C'][104] + 20) / (11 * prices['FALCON-C'][104])
    prices['FALCON-C'][105:] *= rights_factor
    prices['FALCON-C'][130:] /= 2
    histories = {
        ticker: pd.DataFrame({'Date': dates, 'Ticker': ticker, 'Close': values,
                              'Volume': 100_000 + (step * (index + 1) * 271) % 80_000})
        for index, (ticker, values) in enumerate(prices.items())
    }
    actions = pd.DataFrame([
        {'Date': dates[55], 'Ticker': 'FALCON-A', 'Cash Dividend per Share': 1.50,
         'Source': 'Fictional demo notice'},
        {'Date': dates[80], 'Ticker': 'FALCON-B', 'Stock Dividend %': 5.0,
         'Source': 'Fictional demo notice'},
        {'Date': dates[105], 'Ticker': 'FALCON-C', 'Rights New Shares': 1.0,
         'Rights Held Shares': 10.0, 'Rights Price': 20.0,
         'Source': 'Fictional demo notice'},
        {'Date': dates[130], 'Ticker': 'FALCON-C', 'Split New Shares': 2.0,
         'Split Old Shares': 1.0, 'Source': 'Fictional demo notice'},
    ]).reindex(columns=ACTION_COLUMNS)
    return histories, actions


with st.expander('Saved portfolios', expanded=False):
    saved = repository().list_portfolios()
    if saved:
        chosen_id = st.selectbox('Saved portfolio', [item['id'] for item in saved],
                                 format_func=lambda value: next(item['name'] for item in saved
                                                                if item['id'] == value),
                                 key='saved_portfolio_picker')
        selected_name = next(item['name'] for item in saved if item['id'] == chosen_id)
        renamed = st.text_input('Selected portfolio name', value=selected_name,
                                key=f'portfolio_rename_{chosen_id}')
        open_col, rename_col, copy_col, delete_col = st.columns(4)
        if open_col.button('Open', width='stretch'):
            meta, payload = repository().open_portfolio(chosen_id)
            restore_portfolio(meta, payload)
            st.rerun()
        if rename_col.button('Rename', width='stretch'):
            try:
                repository().rename_portfolio(chosen_id, renamed)
                st.success('Portfolio renamed.')
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if copy_col.button('Duplicate', width='stretch'):
            new_id = repository().duplicate_portfolio(chosen_id)
            st.success(f'Created portfolio copy #{new_id}.')
            st.rerun()
        if delete_col.button('Delete', width='stretch'):
            repository().delete_portfolio(chosen_id)
            if st.session_state.get('portfolio_saved_id') == chosen_id:
                st.session_state.pop('portfolio_saved_id', None)
            st.success('Deleted the saved portfolio.')
            st.rerun()
    else:
        st.info('No saved portfolios yet. Load prices, review the inputs, then save below.')


exchange = st.selectbox('Exchange', ['DSE', 'CSE'], key='portfolio_exchange')
catalog = bundled_ticker_catalog(exchange)
tickers = st.multiselect(
    'Stocks', list(catalog), default=['SQURPHARMA'] if 'SQURPHARMA' in catalog else [],
    accept_new_options=True, max_selections=20, placeholder='Type ticker or company name',
    format_func=lambda value: f'{value} — {catalog[value]}' if catalog.get(value) else value,
    help='Choose up to 20 stocks. You can also type a ticker manually and press Enter.')
tickers = list(dict.fromkeys(str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()))

today = date.today()
period_col1, period_col2, frequency_col = st.columns(3)
start = period_col1.date_input('From', today - timedelta(days=365), max_value=today,
                               key='portfolio_start')
end = period_col2.date_input('To', today, max_value=today, key='portfolio_end')
frequency = frequency_col.selectbox('Return frequency', ['Daily', 'Weekly', 'Monthly'], index=2,
                                     key='portfolio_frequency')

fetch_col, demo_col = st.columns(2)
if fetch_col.button('Fetch price data for selected stocks', type='primary', disabled=not tickers,
                    width='stretch'):
    histories, sources, failures = {}, {}, []
    for ticker in tickers:
        try:
            history, source = cached_history(exchange, ticker, start, end)
            histories[ticker] = history
            sources[ticker] = source
        except ValueError as exc:
            failures.append(f'{ticker}: {exc}')
    if histories:
        st.session_state.portfolio_histories = histories
        st.session_state.portfolio_sources = sources
        st.session_state.portfolio_history_key = (exchange, tuple(tickers), start, end)
        st.session_state.portfolio_fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        st.success(f'Loaded price history for {len(histories)} stock(s).')
    for failure in failures:
        st.error(failure)

if demo_col.button('Load fictional sample portfolio', width='stretch'):
    demo_histories, demo_actions = demo_portfolio()
    st.session_state.portfolio_histories = demo_histories
    st.session_state.portfolio_sources = {ticker: 'Fictional bundled portfolio demo'
                                          for ticker in demo_histories}
    st.session_state.portfolio_history_key = ('DEMO', tuple(demo_histories),
                                              min(frame.Date.min() for frame in demo_histories.values()),
                                              max(frame.Date.max() for frame in demo_histories.values()))
    st.session_state.portfolio_fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    st.session_state.portfolio_actions = demo_actions
    st.session_state.pop('portfolio_analysis', None)
    st.rerun()

with st.expander('Price-data upload fallback'):
    st.write('Upload a combined CSV/XLSX with Date, Ticker, Close and Volume columns when an exchange blocks live access.')
    upload = st.file_uploader('Combined price-history file', type=['csv', 'xlsx'], key='portfolio_price_file')
    if upload and st.button('Use uploaded portfolio prices'):
        try:
            combined = read_price_file(upload.getvalue(), upload.name, tickers[0] if len(tickers) == 1 else '')
            found = sorted(combined['Ticker'].astype(str).str.upper().unique())
            chosen = tickers or found
            histories = {ticker: combined[combined['Ticker'].astype(str).str.upper().eq(ticker)].copy()
                         for ticker in chosen}
            histories = {ticker: frame for ticker, frame in histories.items() if not frame.empty}
            if not histories:
                raise ValueError('The file has no rows for the selected tickers.')
            st.session_state.portfolio_histories = histories
            st.session_state.portfolio_sources = {ticker: f'User upload: {upload.name}' for ticker in histories}
            st.session_state.portfolio_history_key = (exchange, tuple(chosen), start, end)
            st.session_state.portfolio_fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            st.success(f'Loaded uploaded prices for {len(histories)} stock(s).')
        except ValueError as exc:
            st.error(str(exc))

histories = st.session_state.get('portfolio_histories', {})
if histories:
    available = list(histories)
    st.subheader('Price history')
    close_frames = []
    for ticker, frame in histories.items():
        series = frame[['Date', 'Close']].copy()
        series['Ticker'] = ticker
        close_frames.append(series)
    combined_close = pd.concat(close_frames, ignore_index=True)
    st.line_chart(combined_close.pivot_table(index='Date', columns='Ticker', values='Close', aggfunc='last'),
                  y_label='Close price (BDT)')
    fetched_at = st.session_state.get('portfolio_fetched_at', '')
    source_rows = [{'Ticker': ticker, 'Status': 'Fictional demo' if 'Fictional' in
                    st.session_state.get('portfolio_sources', {}).get(ticker, '') else 'Loaded — verify source',
                    'Source': st.session_state.get('portfolio_sources', {}).get(ticker, ''),
                    'Retrieved UTC': fetched_at,
                    'Rows': len(frame), 'From': pd.to_datetime(frame.Date).min().date(),
                    'To': pd.to_datetime(frame.Date).max().date()}
                   for ticker, frame in histories.items()]
    st.dataframe(pd.DataFrame(source_rows), hide_index=True, width='stretch')
    st.caption('Source badges describe origin and retrieval time; they do not certify completeness or accuracy.')

    st.subheader('Corporate actions')
    st.write('Exchange figures below are references. Add the verified effective/record date and terms to the calculation table.')
    if st.button('Load available exchange dividend references'):
        references, failures = [], []
        for ticker in available:
            try:
                annual = cached_dividend_reference(exchange, ticker)
                detail = annual.details[annual.details['Exchange metric'].isin(['Dividend', 'Dividend Yield'])].copy()
                detail.insert(0, 'Ticker', ticker)
                references.append(detail)
            except ValueError as exc:
                failures.append(f'{ticker}: {exc}')
        st.session_state.portfolio_dividend_reference = (
            pd.concat(references, ignore_index=True) if references else pd.DataFrame())
        for failure in failures:
            st.error(failure)
    reference = st.session_state.get('portfolio_dividend_reference')
    if isinstance(reference, pd.DataFrame) and not reference.empty:
        st.dataframe(reference, hide_index=True, width='stretch')

    action_key = 'portfolio_actions'
    if action_key not in st.session_state:
        st.session_state[action_key] = pd.DataFrame([
            {**{column: 0.0 for column in ACTION_COLUMNS}, 'Date': pd.NaT,
             'Ticker': ticker, 'Source': ''} for ticker in available
        ]).reindex(columns=ACTION_COLUMNS)
    actions = st.data_editor(
        st.session_state[action_key], num_rows='dynamic', hide_index=True, width='stretch',
        column_config={
            'Date': st.column_config.DateColumn('Effective / record date'),
            'Ticker': st.column_config.SelectboxColumn('Ticker', options=available, required=True),
            'Cash Dividend per Share': st.column_config.NumberColumn('Cash dividend / share (BDT)', min_value=0.0),
            'Cash Dividend %': st.column_config.NumberColumn('Cash dividend %', min_value=0.0),
            'Face Value': st.column_config.NumberColumn('Face value (BDT)', min_value=0.0),
            'Stock Dividend %': st.column_config.NumberColumn('Stock dividend %', min_value=0.0),
            'Rights New Shares': st.column_config.NumberColumn('Rights: new shares', min_value=0.0),
            'Rights Held Shares': st.column_config.NumberColumn('Rights: shares held', min_value=0.0),
            'Rights Price': st.column_config.NumberColumn('Rights price (BDT)', min_value=0.0),
            'Split New Shares': st.column_config.NumberColumn('Split: new shares', min_value=0.0),
            'Split Old Shares': st.column_config.NumberColumn('Split: old shares', min_value=0.0),
            'Source': st.column_config.TextColumn('Source / notice reference'),
        }, key='portfolio_action_editor')
    st.session_state[action_key] = actions

    st.subheader('Holdings and transaction costs')
    if 'portfolio_holdings' not in st.session_state or set(
            st.session_state.portfolio_holdings.get('Ticker', [])) != set(available):
        st.session_state.portfolio_holdings = pd.DataFrame([
            {'Ticker': ticker, 'Initial Shares': 1.0,
             'Purchase Price': float(pd.to_numeric(histories[ticker]['Close']).iloc[0]),
             'Initial Fees': 0.0, 'Exit Fees': 0.0} for ticker in available
        ], columns=HOLDING_COLUMNS)
    holdings_edited = st.data_editor(
        st.session_state.portfolio_holdings, hide_index=True, width='stretch', disabled=['Ticker'],
        column_config={
            'Initial Shares': st.column_config.NumberColumn('Starting shares', min_value=0.000001),
            'Purchase Price': st.column_config.NumberColumn('Purchase price / share (BDT)', min_value=0.000001),
            'Initial Fees': st.column_config.NumberColumn('Purchase fees (BDT)', min_value=0.0),
            'Exit Fees': st.column_config.NumberColumn('Estimated sale fees (BDT)', min_value=0.0),
        }, key='portfolio_holding_editor')
    st.session_state.portfolio_holdings = holdings_edited
    st.caption('Purchase price controls the holding-period cost basis. Periodic volatility still uses the selected price-history period.')

    st.subheader('Portfolio weights and risk settings')
    default_weight = 100 / len(available)
    saved_weights = st.session_state.get('portfolio_weights')
    weight_frame = (saved_weights if isinstance(saved_weights, pd.DataFrame)
                    and set(saved_weights.get('Ticker', [])) == set(available)
                    else pd.DataFrame({'Ticker': available, 'Weight %': [default_weight] * len(available)}))
    weights_edited = st.data_editor(
        weight_frame, hide_index=True, width='stretch', disabled=['Ticker'],
        column_config={'Weight %': st.column_config.NumberColumn(min_value=0.0, max_value=100.0)},
        key='portfolio_weight_editor')
    st.session_state.portfolio_weights = weights_edited
    total_weight = float(weights_edited['Weight %'].sum())
    st.caption(f'Weights currently total {total_weight:.2f}%. They are normalized to 100% for calculation.')
    risk_col, benchmark_col = st.columns(2)
    risk_free_percent = risk_col.number_input(
        'Annual risk-free reference rate %', min_value=0.0, max_value=100.0,
        step=.25, key='portfolio_risk_free',
        help='Enter the reviewed annual reference rate used for Sharpe and Sortino ratios. The app does not assume a current market rate.')
    benchmark = benchmark_col.selectbox(
        'Comparison benchmark', ['Equal-weight basket', *available], key='portfolio_benchmark',
        help='Choose one selected stock or an equal-weight basket as a simple return reference.')

    if st.button('Calculate portfolio return and risk', type='primary'):
        try:
            weights = dict(zip(weights_edited.Ticker, weights_edited['Weight %']))
            st.session_state.portfolio_analysis = analyze_portfolio(
                histories, actions, weights, frequency, holdings_edited, risk_free_percent / 100)
            st.session_state.portfolio_analysis_frequency = frequency
            st.session_state.portfolio_analysis_benchmark = benchmark
        except ValueError as exc:
            st.error(str(exc))

    st.markdown('**Save this portfolio workspace**')
    save_name = st.text_input('Portfolio name', value=st.session_state.get(
        'portfolio_name', f'{exchange} portfolio'), key='portfolio_name_input')
    save_col, save_copy_col = st.columns(2)
    if save_col.button('Save portfolio', width='stretch'):
        try:
            payload = portfolio_payload(histories, actions, holdings_edited, weights_edited,
                                        exchange, frequency, risk_free_percent / 100)
            saved_id = repository().save_portfolio(
                save_name, payload, st.session_state.get('portfolio_saved_id'))
            st.session_state.portfolio_saved_id = saved_id
            st.session_state.portfolio_name = save_name
            st.success('Portfolio saved on this device.')
        except ValueError as exc:
            st.error(str(exc))
    if save_copy_col.button('Save as new copy', width='stretch'):
        try:
            payload = portfolio_payload(histories, actions, holdings_edited, weights_edited,
                                        exchange, frequency, risk_free_percent / 100)
            saved_id = repository().save_portfolio(save_name, payload)
            st.session_state.portfolio_saved_id = saved_id
            st.session_state.portfolio_name = save_name
            st.success('Saved as a new portfolio.')
        except ValueError as exc:
            st.error(str(exc))

analysis = st.session_state.get('portfolio_analysis')
if analysis is not None and not {'Sharpe Ratio', 'Total Invested'}.issubset(
        analysis.portfolio_summary):
    st.session_state.pop('portfolio_analysis', None)
    analysis = None
    st.info('Portfolio inputs were upgraded. Calculate again to refresh the expanded risk and holdings results.')
if analysis is not None:
    st.divider()
    st.subheader('Portfolio results')
    summary = analysis.portfolio_summary
    metric_cols = st.columns(4)
    metric_cols[0].metric('Annualized average return', f'{summary["Annualized Average Return"]:.2%}')
    metric_cols[1].metric('Annualized volatility', f'{summary["Annualized Volatility"]:.2%}')
    metric_cols[2].metric('Average periodic return', f'{summary["Average Return"]:.3%}')
    metric_cols[3].metric('Aligned observations', f'{int(summary["Observations"]):,}')

    value_cols = st.columns(4)
    value_cols[0].metric('Total invested', f'BDT {summary["Total Invested"]:,.2f}')
    value_cols[1].metric('Current value', f'BDT {summary["Current Value"]:,.2f}')
    value_cols[2].metric('Cash dividends', f'BDT {summary["Total Cash Dividends"]:,.2f}')
    value_cols[3].metric('Total gain', f'BDT {summary["Total Gain"]:,.2f}')

    risk_cols = st.columns(4)
    risk_cols[0].metric('Sharpe ratio', f'{summary["Sharpe Ratio"]:.2f}')
    risk_cols[1].metric('Sortino ratio', f'{summary["Sortino Ratio"]:.2f}')
    risk_cols[2].metric('Maximum drawdown', f'{summary["Maximum Drawdown"]:.2%}')
    risk_cols[3].metric('Historical VaR (95%)', f'{summary["Historical VaR 95%"]:.2%}',
                        help='Estimated one-period loss threshold from the worst 5% of observed portfolio returns.')

    with st.expander('Understand these risk measures'):
        st.markdown('''
- **Sharpe ratio** compares annualized return above the entered risk-free rate with total volatility.
- **Sortino ratio** focuses on harmful downside volatility.
- **Maximum drawdown** is the largest peak-to-trough decline in the analyzed return path.
- **Historical VaR (95%)** is the one-period loss threshold exceeded by roughly 5% of observations. It is not a worst-case loss.
''')

    benchmark_name = st.session_state.get('portfolio_analysis_benchmark', 'Equal-weight basket')
    benchmark_returns = (analysis.periodic_returns.mean(axis=1) if benchmark_name == 'Equal-weight basket'
                         else analysis.periodic_returns[benchmark_name])
    portfolio_total = (1 + analysis.portfolio_returns).cumprod() - 1
    benchmark_total = (1 + benchmark_returns).cumprod() - 1
    comparison = pd.DataFrame({'Portfolio': portfolio_total, benchmark_name: benchmark_total})
    st.markdown(f'**Cumulative return versus {benchmark_name}**')
    st.line_chart(comparison, y_label='Cumulative return')
    benchmark_variance = benchmark_returns.var(ddof=1)
    beta = (analysis.portfolio_returns.cov(benchmark_returns) / benchmark_variance
            if benchmark_variance and not pd.isna(benchmark_variance) else np.nan)
    relative_cols = st.columns(3)
    relative_cols[0].metric('Portfolio cumulative return', f'{portfolio_total.iloc[-1]:.2%}')
    relative_cols[1].metric('Benchmark cumulative return', f'{benchmark_total.iloc[-1]:.2%}')
    relative_cols[2].metric('Beta to benchmark', 'N/A' if pd.isna(beta) else f'{beta:.2f}')

    st.markdown('**Holding-period return by stock**')
    percent_columns = ['Dividend Yield', 'Capital Gain %', 'Total Return %', 'Price Return %']
    st.dataframe(analysis.asset_summary.style.format(
        {**{column: '{:.2%}' for column in percent_columns},
         **{column: '{:,.2f}' for column in ['Start Close', 'End Close', 'Ending Shares',
                                             'Initial Shares', 'Purchase Price', 'Initial Cost',
                                             'Current Value', 'Transaction Fees', 'Cash Dividends',
                                             'Rights Investment', 'Capital Gain']}}),
        hide_index=True, width='stretch')

    st.markdown(f'**Risk statistics ({st.session_state.get("portfolio_analysis_frequency", "periodic").lower()} returns)**')
    st.dataframe(analysis.risk_summary.style.format({
        'Average Return': '{:.3%}', 'Standard Deviation': '{:.3%}', 'Variance': '{:.6f}',
        'Annualized Average Return': '{:.2%}', 'Annualized Volatility': '{:.2%}',
        'Sharpe Ratio': '{:.2f}', 'Sortino Ratio': '{:.2f}', 'Maximum Drawdown': '{:.2%}',
        'Weight': '{:.2%}'}),
        hide_index=True, width='stretch')

    covariance_tab, annual_tab = st.tabs(['Covariance matrix', 'Annualized covariance'])
    with covariance_tab:
        st.dataframe(analysis.covariance.style.format('{:.6f}'), width='stretch')
    with annual_tab:
        st.dataframe(analysis.annualized_covariance.style.format('{:.6f}'), width='stretch')

    st.subheader('Portfolio decision tools')
    risk_tab, allocation_tab, actions_tab = st.tabs(
        ['Risk contribution', 'Opportunity set & rebalancing', 'Corporate-action timeline'])
    with risk_tab:
        contributions = portfolio_risk_contribution(analysis)
        st.dataframe(contributions.style.format({
            'Weight': '{:.2%}', 'Volatility contribution': '{:.2%}',
            'Share of portfolio risk': '{:.2%}'}), hide_index=True, width='stretch')
        st.bar_chart(contributions.set_index('Ticker')['Share of portfolio risk'])
        st.caption('Risk contribution can differ greatly from capital weight when assets have different volatility or correlations.')
    with allocation_tab:
        frontier = efficient_frontier(analysis, float(summary['Risk Free Rate']))
        min_risk = frontier.loc[frontier['Annualized Volatility'].idxmin()]
        valid_sharpe = frontier['Sharpe Ratio'].dropna()
        max_sharpe = frontier.loc[valid_sharpe.idxmax()] if not valid_sharpe.empty else min_risk
        choice = st.radio('Illustrative target', ['Minimum volatility', 'Highest simulated Sharpe'],
                          horizontal=True)
        selected = min_risk if choice == 'Minimum volatility' else max_sharpe
        weight_columns = [column for column in frontier if column.startswith('Weight · ')]
        targets = {column.removeprefix('Weight · '): float(selected[column]) for column in weight_columns}
        target_table = pd.DataFrame({'Ticker': list(targets), 'Target weight': list(targets.values())})
        st.dataframe(target_table.style.format({'Target weight': '{:.2%}'}), hide_index=True, width='stretch')
        values = analysis.asset_summary.set_index('Ticker')['Current Value'].to_dict()
        plan = rebalance_plan(values, targets)
        st.dataframe(plan.style.format({
            'Current value': 'BDT {:,.0f}', 'Current weight': '{:.2%}', 'Target weight': '{:.2%}',
            'Target value': 'BDT {:,.0f}', 'Indicative trade': 'BDT {:+,.0f}'}),
            hide_index=True, width='stretch')
        chart_data = frontier[['Annualized Volatility', 'Annualized Return']].copy()
        st.scatter_chart(chart_data, x='Annualized Volatility', y='Annualized Return')
        st.caption('The opportunity set is a deterministic simulation from historical estimates. Trades exclude taxes, liquidity, lot sizes and market impact and require human approval.')
    with actions_tab:
        reviewed_actions = st.session_state.get('portfolio_actions')
        if isinstance(reviewed_actions, pd.DataFrame) and not reviewed_actions.empty:
            timeline = reviewed_actions.copy().sort_values('Date')
            st.dataframe(timeline, hide_index=True, width='stretch')
        else:
            st.info('No corporate actions were entered for this analysis period.')

    heatmap = go.Figure(go.Heatmap(
        z=analysis.covariance.values, x=analysis.covariance.columns,
        y=analysis.covariance.index, colorscale='Teal', text=analysis.covariance.round(6).values,
        texttemplate='%{text}', hovertemplate='%{y} × %{x}<br>%{z:.6f}<extra></extra>'))
    heatmap.update_layout(title='Return covariance', height=420, margin=dict(l=20, r=20, t=55, b=20),
                          template='plotly_dark' if st.session_state.get('dark') else 'plotly_white')
    st.plotly_chart(heatmap, width='stretch', config={'displaylogo': False})
    report_name = st.session_state.get('portfolio_name', 'Portfolio analysis')
    report_bytes = portfolio_report_html(
        report_name, analysis, st.session_state.get('portfolio_sources', {}),
        st.session_state.get('portfolio_analysis_frequency', 'Periodic'))
    st.download_button('Download reviewable portfolio report', report_bytes,
                       file_name='Falcon_Finalysis_Portfolio_Report.html', mime='text/html',
                       width='stretch')
    st.caption('Average return, volatility, variance and covariance use aligned observations only. Total return includes entered cash dividends, stock dividends, subscribed rights and splits. Entered transaction fees are included in holding-period values; taxes and dividend reinvestment are excluded.')
