"""Independent expected-value and edge-case checks for financial policies."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from core.ratio_engine import calculate
from core.dupont_engine import dupont, attribution
from core.trend_engine import cagr, growth, describe
from core.health_score import health_score, POLICY
from core.scenario_engine import baseline, model, sensitivity
from core.validation import validate
from core.financial_engine import analyze
from core.portfolio_engine import (analyze_portfolio, efficient_frontier,
                                   portfolio_risk_contribution, rebalance_plan)
from core.credit_engine import analyze_credit
from core.data_quality import assess_financial_data
from core.valuation_engine import (calculate_wacc, comparable_valuation,
                                   discounted_cash_flow, roic_reinvestment)
from data.credit_data import evidence_checks, read_transaction_file, suggest_transaction_categories
from data.demo import demo_company
from data.parsers import prepare, read_file
from data.database import Repository


@pytest.fixture
def known():
    rows = []
    for year in [2023, 2024, 2025]:
        rows.append(dict(Year=year, Revenue=1000, COGS=600, **{
            'Gross Profit': 400, 'Operating Expenses': 200, 'EBITDA': 200,
            'Depreciation': 50, 'EBIT': 150, 'Interest Expense': 30, 'EBT': 120,
            'Tax Expense': 30, 'Net Income': 90, 'Total Assets': 1000 if year == 2023 else 1200,
            'Shareholders Equity': 400 if year == 2023 else 600, 'Total Current Assets': 400,
            'Total Current Liabilities': 200, 'Inventory': 100, 'Accounts Receivable': 100,
            'Accounts Payable': 60, 'Cash': 80, 'Short-Term Debt': 100, 'Long-Term Debt': 200,
            'Total Liabilities': 600, 'Operating Cash Flow': 120, 'Capital Expenditure': 40,
            'Cash Dividends': 18, 'Preferred Dividends': 0, 'Shares Outstanding': 30,
            'Weighted Average Shares Outstanding': 20, 'Market Price Per Share': 45}))
    return pd.DataFrame(rows)


@pytest.mark.parametrize('metric,expected', [
    ('Current Ratio', 2), ('Quick Ratio', 1.5), ('Cash Ratio', .4), ('Operating Cash Flow Ratio', .6),
    ('Gross Profit Margin', .4), ('Net Profit Margin', .09), ('Operating Margin', .15),
    ('ROA', 90/1100), ('ROE', 90/500), ('Debt-to-Equity', .5), ('Liabilities-to-Equity', 1),
    ('Interest Coverage', 5), ('Asset Turnover', 1000/1100), ('Inventory Days', 365/6),
    ('Receivable Days', 36.5), ('Payable Days', 36.5), ('Cash Conversion Cycle', 365/6),
    ('Free Cash Flow', 80), ('EPS', 4.5), ('P/E Ratio', 10), ('Dividend Yield', .6/45),
])
def test_known_ratios(known, metric, expected):
    ratios, _ = calculate(known)
    assert ratios.loc[2024, metric] == pytest.approx(expected)


def test_average_fallback_and_missing(known):
    ratios, _ = calculate(known)
    assert ratios.loc[2023, 'ROA'] == .09
    known.loc[0, 'Total Assets'] = np.nan
    ratios, why = calculate(known)
    assert np.isnan(ratios.loc[2024, 'ROA'])
    assert why.loc[2024, 'ROA']


def test_zero_negative_missing(known):
    known.loc[2, 'Total Current Liabilities'] = 0
    known.loc[2, 'Shareholders Equity'] = -50
    known.loc[2, 'Interest Expense'] = 0
    ratios, why = calculate(known)
    for metric in ['Current Ratio', 'ROE', 'Debt-to-Equity', 'Interest Coverage', 'Book Value Per Share']:
        assert np.isnan(ratios.loc[2025, metric])
        assert why.loc[2025, metric]
    assert not np.isinf(ratios.to_numpy()).any()


def test_dupont_exact(known):
    ratios, _ = calculate(known)
    result = dupont(known, ratios)
    assert result.loc[2024, 'DuPont ROE'] == pytest.approx(.18)
    assert result['DuPont ROE'].values == pytest.approx(ratios['ROE'].values)
    assert attribution(result).sum() == pytest.approx(result['DuPont ROE'].diff().iloc[-1])


def test_cagr_and_growth():
    series = pd.Series([100, 110, 121], index=[2023, 2024, 2025])
    assert cagr(series) == pytest.approx(.1)
    assert np.isnan(cagr(pd.Series([-1, 2, 3], index=series.index)))
    assert np.isnan(growth(pd.Series([0, 2])).iloc[-1])
    assert describe(series)['3-year direction'] == 'Improving'
    assert describe(pd.Series([100, 200, 90]))['3-year direction'] == 'Mixed trend'


def test_portfolio_returns_include_dividends_bonus_shares_and_risk():
    dates = pd.to_datetime(['2025-01-01', '2025-01-02', '2025-01-03'])
    histories = {
        'AAA': pd.DataFrame({'Date': dates, 'Ticker': 'AAA',
                             'Close': [100, 100 / 1.1, 100], 'Volume': 1000}),
        'BBB': pd.DataFrame({'Date': dates, 'Ticker': 'BBB',
                             'Close': [100, 110, 121], 'Volume': 1000}),
    }
    actions = pd.DataFrame([{
        'Date': dates[1], 'Ticker': 'AAA', 'Cash Dividend per Share': 2,
        'Stock Dividend %': 10, 'Source': 'Test notice',
    }])
    result = analyze_portfolio(histories, actions, {'AAA': 60, 'BBB': 40}, 'Daily')
    aaa = result.asset_summary.set_index('Ticker').loc['AAA']
    assert aaa['Cash Dividends'] == pytest.approx(2)
    assert aaa['Ending Shares'] == pytest.approx(1.1)
    assert aaa['Total Return %'] == pytest.approx(.12)
    assert result.risk_summary.set_index('Ticker').loc['AAA', 'Weight'] == pytest.approx(.6)
    assert result.covariance.shape == (2, 2)
    assert len(result.portfolio_returns) == 2


def test_portfolio_holdings_costs_and_advanced_risk():
    dates = pd.bdate_range('2025-01-01', periods=8)
    histories = {
        'AAA': pd.DataFrame({'Date': dates, 'Ticker': 'AAA',
                             'Close': [100, 102, 101, 104, 103, 106, 105, 108]}),
        'BBB': pd.DataFrame({'Date': dates, 'Ticker': 'BBB',
                             'Close': [50, 49, 51, 50, 52, 51, 53, 54]}),
    }
    holdings = pd.DataFrame([
        {'Ticker': 'AAA', 'Initial Shares': 10, 'Purchase Price': 95,
         'Initial Fees': 10, 'Exit Fees': 5},
        {'Ticker': 'BBB', 'Initial Shares': 20, 'Purchase Price': 48,
         'Initial Fees': 8, 'Exit Fees': 4},
    ])
    result = analyze_portfolio(histories, weights={'AAA': 50, 'BBB': 50},
                               holdings=holdings, risk_free_rate=.05)
    aaa = result.asset_summary.set_index('Ticker').loc['AAA']
    assert aaa['Initial Cost'] == pytest.approx(960)
    assert aaa['Current Value'] == pytest.approx(1075)
    assert aaa['Transaction Fees'] == 15
    assert result.portfolio_summary['Total Invested'] == pytest.approx(1928)
    assert np.isfinite(result.portfolio_summary['Sharpe Ratio'])
    assert result.portfolio_summary['Maximum Drawdown'] <= 0
    assert result.portfolio_summary['Historical VaR 95%'] >= 0
    contributions = portfolio_risk_contribution(result)
    assert contributions['Share of portfolio risk'].sum() == pytest.approx(1)
    frontier = efficient_frontier(result, .05, 200)
    assert len(frontier) == 200
    assert {'Annualized Return', 'Annualized Volatility', 'Sharpe Ratio'} <= set(frontier)
    plan = rebalance_plan({'AAA': 1_000, 'BBB': 500}, {'AAA': .5, 'BBB': .5})
    assert plan['Indicative trade'].sum() == pytest.approx(0)


def test_saved_portfolio_crud(tmp_path):
    repo = Repository(tmp_path/'portfolios.db')
    payload = {'exchange': 'DSE', 'histories': {'AAA': [{'Date': '2025-01-01', 'Close': 10}]}}
    portfolio_id = repo.save_portfolio('Income portfolio', payload)
    assert repo.open_portfolio(portfolio_id)[1] == payload
    repo.rename_portfolio(portfolio_id, 'Renamed portfolio')
    copied = repo.duplicate_portfolio(portfolio_id)
    assert repo.open_portfolio(copied)[0]['name'] == 'Renamed portfolio (copy)'
    repo.delete_portfolio(portfolio_id)
    assert [item['id'] for item in repo.list_portfolios()] == [copied]


def test_credit_analysis_is_explainable_and_benchmark_linked():
    dates = pd.date_range('2025-01-01', periods=8, freq='MS')
    rows = []
    for index, month in enumerate(dates):
        rows.extend([
            {'Date': month, 'Amount': 120_000 + index * 2_000, 'Balance': 100_000},
            {'Date': month + pd.Timedelta(days=10), 'Amount': -80_000, 'Balance': 60_000},
        ])
    result = analyze_credit(pd.DataFrame(rows), 250_000, 12, 5_000, 1.3,
                            .10, .03, .02, .04, .8)
    assert result.score is not None and 0 <= result.score <= 100
    assert result.components['Weight'].sum() == 100
    assert result.proposal['Annual Proposed Rate'] == pytest.approx(.19)
    assert result.proposal['Annual Proposed Rate'] > result.proposal['Risk Free Rate']
    assert result.proposal['Recommended Amount'] <= 250_000
    assert result.proposal['Post Loan DSCR'] >= 1.3
    assert result.reasons


def test_credit_withholds_score_for_short_history_and_requires_premium():
    transactions = pd.DataFrame({'Date': ['2025-01-01', '2025-02-01'],
                                 'Amount': [100_000, 110_000]})
    result = analyze_credit(transactions, 100_000, 6, 0, 1.2, .1, .01, .01, .02, .5)
    assert result.score is None
    assert result.proposal['Recommended Amount'] == 0
    with pytest.raises(ValueError, match='premium'):
        analyze_credit(transactions, 100_000, 6, 0, 1.2, .1, 0, 0, 0, .5)


def test_credit_transaction_csv_and_decision_audit(tmp_path):
    content = (b'Transaction Date,Narration,Credit,Debit,Running Balance\n'
               b'01/01/2025,Sales,100000,,120000\n02/01/2025,Rent,,20000,100000\n')
    frame = read_transaction_file(content, 'statement.csv')
    assert frame['Amount'].tolist() == [100_000, -20_000]
    repo = Repository(tmp_path/'credit.db')
    case_id = repo.save_credit_case('Small shop', {'transactions': []})
    decision_id = repo.save_credit_decision(case_id, 'Modify', 'R-101',
                                             'Reduced to verified capacity.', {'amount': 50_000})
    assert decision_id > 0
    assert repo.credit_decisions(case_id)[0]['decision'] == 'Modify'
    categorized = suggest_transaction_categories(frame)
    assert categorized['Category'].tolist() == ['Business revenue', 'Rent']
    assert set(evidence_checks(categorized)['Status']) <= {'OK', 'INFO', 'REVIEW'}


def test_data_quality_mapping_settings_and_audit(tmp_path):
    frame = demo_company()
    report = assess_financial_data(frame)
    assert 0 <= report.score <= 100
    assert report.coverage > 0
    repo = Repository(tmp_path/'governance.db')
    mapping_id = repo.save_import_mapping('Annual export', {'Fiscal Year': 'Year', 'Sales': 'Revenue'})
    assert repo.open_import_mapping(mapping_id)['Sales'] == 'Revenue'
    repo.save_settings({'retention_days': '365', 'reviewer_role': 'Credit reviewer'})
    assert repo.settings()['retention_days'] == '365'
    assert repo.audit_events()[0]['object_type'] == 'Local settings'


def test_public_company_valuation_math():
    wacc = calculate_wacc(900, 100, .08, .06, 1.0, .10, .25)
    assert wacc.cost_of_equity == pytest.approx(.14)
    assert wacc.wacc == pytest.approx(.1335)
    dcf = discounted_cash_flow(100, [.10] * 5, wacc.wacc, .04, 50, 100, 10)
    assert dcf.enterprise_value > 0
    assert dcf.value_per_share == pytest.approx((dcf.enterprise_value - 50) / 10)
    assert dcf.sensitivity.shape == (5, 5)
    peers = pd.DataFrame({'EV/Revenue': [2, 3, 4], 'EV/EBITDA': [8, 10, 12],
                          'P/E': [14, 16, 18]})
    comps = comparable_valuation(peers, 500, 100, 50, 100, 50, 10)
    median_pe = comps[(comps.Method == 'P/E') & (comps.Case == 'Median')].iloc[0]
    assert median_pe['Implied value per share'] == pytest.approx(80)
    screening = roic_reinvestment(demo_company(), .25)
    assert {'ROIC', 'Reinvestment Rate', 'Intrinsic Growth'} <= set(screening)
    assert len(screening) == 5


def test_industry_suggestions_and_aligned_exchange_comparison():
    from core.comparison_engine import comparison_strengths, exchange_metric_comparison
    from data.industry_catalog import industry_for_ticker, suggested_peers

    assert industry_for_ticker('OLYMPIC') == 'Foods & Allied'
    assert suggested_peers('OLYMPIC', available={'OLYMPIC', 'RDFOOD', 'LOVELLO'}) == [
        'LOVELLO', 'RDFOOD']
    details = {
        'OLYMPIC': pd.DataFrame([
            {'Year': 2024, 'Exchange metric': 'Basic EPS', 'Value': 9.0},
            {'Year': 2025, 'Exchange metric': 'Basic EPS', 'Value': 10.5},
            {'Year': 2025, 'Exchange metric': 'NAV per Share', 'Value': 42.0},
        ]),
        'RDFOOD': pd.DataFrame([
            {'Year': 2025, 'Exchange metric': 'Basic EPS', 'Value': 2.5},
            {'Year': 2025, 'Exchange metric': 'NAV per Share', 'Value': 18.0},
        ]),
    }
    comparison = exchange_metric_comparison(details)
    assert comparison['Year'].eq(2025).all()
    assert comparison.loc['OLYMPIC', 'Basic EPS'] == pytest.approx(10.5)
    leaders = comparison_strengths(comparison[['Basic EPS', 'NAV per Share']],
                                   ['Basic EPS', 'NAV per Share'])
    assert set(leaders['Reference leader']) == {'OLYMPIC'}


def test_health_bounds_and_coverage():
    best, worst = {}, {}
    for _, (_, rules) in POLICY.items():
        for metric, low, high, inverse in rules:
            best[metric], worst[metric] = (low, high) if inverse else (high, low)
    assert health_score(pd.Series(best)).score == 100
    assert health_score(pd.Series(worst)).score == 0
    assert health_score(pd.Series(dtype=float)).score is None
    assert health_score(pd.Series(best)).coverage == 1


def test_scenario_known(known):
    row = known.iloc[-1]
    base = baseline(row)
    result = model(row, base)
    assert result['Net Income'] == pytest.approx(90)
    assert result['Operating Cash Flow proxy'] == pytest.approx(140)
    assert result['Free Cash Flow'] == pytest.approx(100)
    changed = model(row, replace(base, revenue_growth=.15))
    assert changed['Revenue'] == 1150
    assert changed['EBITDA'] == pytest.approx(230)
    assert changed['Net Income'] == pytest.approx(112.5)
    assert changed['Operating Working Capital'] == pytest.approx(161)
    assert changed['Operating Cash Flow proxy'] == pytest.approx(141.5)
    assert model(row, replace(base, receivable_days=base.receivable_days+10))['Net Income'] == 90
    assert len(sensitivity(row, base, 'Net Income')) == 6
    with pytest.raises(ValueError):
        model(row, replace(base, revenue_growth=-1))


def test_demo_reconciles():
    demo = demo_company()
    assert not [x for x in validate(demo) if x.severity in ['ERROR', 'WARNING']]
    result = analyze(demo)
    assert result.health[-1].score is not None
    assert any(f.severity == 'POSITIVE' for f in result.flags)
    assert any(f.severity in ['WARNING', 'WATCH'] for f in result.flags)


@pytest.mark.parametrize('mutation', ['duplicate', 'year_gap', 'text', 'infinity', 'fractional_year'])
def test_validation_errors(mutation):
    demo = demo_company()
    if mutation == 'duplicate':
        demo.loc[1, 'Year'] = 2021
    elif mutation == 'year_gap':
        demo.loc[4, 'Year'] = 2027
    elif mutation == 'text':
        demo['Revenue'] = demo['Revenue'].astype(object)
        demo.loc[0, 'Revenue'] = 'bad'
    elif mutation == 'infinity':
        demo['Revenue'] = demo['Revenue'].astype(float)
        demo.loc[0, 'Revenue'] = np.inf
    else:
        demo['Year'] = demo['Year'].astype(float)
        demo.loc[0, 'Year'] = 2021.5
    assert any(x.severity == 'ERROR' for x in validate(demo))


def test_parser_and_storage(tmp_path):
    demo = demo_company().rename(columns={'Revenue': 'Net Sales'})
    result = prepare(read_file(demo.to_csv(index=False).encode(), 'sample.csv'))
    assert result['Revenue'].iloc[0] == 1_050_000_000
    repo = Repository(tmp_path/'test.db')
    project = repo.save({'company_name': 'Test', 'currency': 'USD'}, result, 'Analysis')
    reopened = Repository(tmp_path/'test.db')
    meta, actual = reopened.open(project)
    assert meta['company_name'] == 'Test'
    assert actual['Revenue'].tolist() == result['Revenue'].tolist()
    copied = repo.duplicate(project)
    repo.rename(copied, 'Copy renamed')
    repo.delete(project)
    assert repo.open(copied)[0]['name'] == 'Copy renamed'
    assert len(repo.list_projects()) == 1


def test_formula_rejection():
    from openpyxl import Workbook
    from io import BytesIO
    book = Workbook()
    book.active.append(['Year', 'Revenue'])
    book.active.append([2025, '=1+1'])
    stream = BytesIO()
    book.save(stream)
    with pytest.raises(ValueError, match='Formula'):
        read_file(stream.getvalue(), 'bad.xlsx')
