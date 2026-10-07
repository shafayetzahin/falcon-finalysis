"""Independent regression cases for calculation defects found in the reliability audit."""
import numpy as np
import pandas as pd
import pytest

from core.comparison_engine import comparison_strengths, exchange_metric_comparison
from core.credit_engine import analyze_credit
from core.dupont_engine import dupont
from core.financial_engine import analyze
from core.portfolio_engine import _periodic, analyze_portfolio, rebalance_plan, efficient_frontier
from core.ratio_engine import calculate
from core.valuation_engine import comparable_valuation, discounted_cash_flow, roic_reinvestment
from data.demo import demo_company


def prices(values, dates=None):
    dates = pd.date_range("2025-01-01", periods=len(values)) if dates is None else dates
    return pd.DataFrame({"Date": dates, "Close": values})


def credit(transactions, **changes):
    arguments = dict(requested_amount=100_000, tenure_months=12, existing_monthly_debt=0,
                     minimum_dscr=1.2, risk_free_rate=.1, operating_premium=.02,
                     liquidity_premium=.01, risk_premium=.03, document_coverage=.8)
    arguments.update(changes)
    return analyze_credit(transactions, **arguments)


def test_portfolio_normalizes_tickers_and_weights_without_silent_zero_returns():
    result = analyze_portfolio({" aaa ": prices([100, 90, 99]), "bbb": prices([100, 100, 100])},
                               weights={"aAa": 60, " BBB ": 40})
    assert result.portfolio_returns.tolist() == pytest.approx([-.06, .06])
    assert result.risk_summary.set_index("Ticker").loc["AAA", "Weight"] == pytest.approx(.6)


def test_portfolio_returns_cover_common_price_intervals():
    dates = pd.date_range("2025-01-01", periods=5)
    result = analyze_portfolio({
        "AAA": prices([100, 110, 121, 133.1, 146.41], dates),
        "BBB": prices([100, 121, 146.41], dates[[0, 2, 4]]),
    })
    assert result.periodic_returns["AAA"].tolist() == pytest.approx([.21, .21])
    assert result.periodic_returns["BBB"].tolist() == pytest.approx([.21, .21])


def test_months_without_return_observations_are_not_fabricated_as_zero():
    returns = pd.DataFrame({"AAA": [.10, .20], "BBB": [np.nan, .05]},
                           index=pd.to_datetime(["2025-01-10", "2025-03-10"]))
    aggregated, periods = _periodic(returns, "Monthly")
    assert periods == 12
    assert len(aggregated) == 2
    assert np.isnan(aggregated.loc["2025-01-31", "BBB"])
    assert aggregated.loc["2025-03-31", "AAA"] == pytest.approx(.20)


def test_drawdown_includes_first_loss_from_initial_capital():
    result = analyze_portfolio({"AAA": prices([100, 80, 70])})
    assert result.portfolio_summary["Maximum Drawdown"] == pytest.approx(-.30)
    assert result.risk_summary.iloc[0]["Maximum Drawdown"] == pytest.approx(-.30)


def test_sortino_measures_shortfall_against_the_risk_free_target():
    result = analyze_portfolio({"AAA": prices([100, 100, 100])}, risk_free_rate=.1)
    assert result.portfolio_summary["Sortino Ratio"] == pytest.approx(-np.sqrt(252))


def test_opportunity_set_sharpe_uses_same_periodic_target_as_portfolio():
    result = analyze_portfolio({'AAA': prices([100, 110, 105, 115],
        pd.date_range('2025-01-31', periods=4, freq='ME'))},
        frequency='Monthly', risk_free_rate=.1)
    frontier = efficient_frontier(result, .1, simulations=100)
    assert frontier['Sharpe Ratio'].tolist() == pytest.approx(
        [result.portfolio_summary['Sharpe Ratio']] * len(frontier))


def test_blank_optional_fees_do_not_poison_holding_results():
    holdings = pd.DataFrame({"Ticker": ["AAA"], "Initial Shares": [2]})
    result = analyze_portfolio({"AAA": prices([100, 110, 120])}, holdings=holdings)
    row = result.asset_summary.iloc[0]
    assert row["Initial Cost"] == 200
    assert row["Current Value"] == 240
    assert row["Transaction Fees"] == 0


@pytest.mark.parametrize("invalid", [np.nan, np.inf, -np.inf, 0, -1])
def test_portfolio_rejects_invalid_prices(invalid):
    with pytest.raises(ValueError, match="finite positive"):
        analyze_portfolio({"AAA": prices([100, invalid, 120])})


@pytest.mark.parametrize("changes", [
    {"Rights New Shares": 1}, {"Split Old Shares": 1},
    {"Cash Dividend %": 10}, {"Cash Dividend per Share": np.inf},
])
def test_incomplete_or_nonfinite_corporate_actions_cannot_be_silently_ignored(changes):
    action = {"Date": "02/01/2025", "Ticker": "AAA", **changes}
    with pytest.raises(ValueError):
        analyze_portfolio({"AAA": prices([100, 110, 120])}, pd.DataFrame([action]))


def test_rights_subscription_and_split_have_zero_return_at_theoretical_prices():
    actions = pd.DataFrame([
        {"Date": "02/01/2025", "Ticker": "AAA", "Rights New Shares": 1,
         "Rights Held Shares": 1, "Rights Price": 20},
        {"Date": "03/01/2025", "Ticker": "AAA", "Split New Shares": 2, "Split Old Shares": 1},
    ])
    result = analyze_portfolio({"AAA": prices([100, 60, 30])}, actions)
    row = result.asset_summary.iloc[0]
    assert row["Ending Shares"] == 4
    assert row["Rights Investment"] == 20
    assert row["Total Return %"] == pytest.approx(0)
    assert result.periodic_returns["AAA"].tolist() == pytest.approx([0, 0])


def test_nonfinite_portfolio_weights_and_allocations_are_rejected():
    with pytest.raises(ValueError, match="finite"):
        analyze_portfolio({"AAA": prices([100, 110, 120])}, weights={"AAA": np.nan})
    with pytest.raises(ValueError, match="finite"):
        rebalance_plan({"AAA": np.inf}, {"AAA": 1})
    with pytest.raises(ValueError, match="unique"):
        analyze_portfolio({"AAA": prices([100, 110, 120]), " aaa ": prices([100, 110, 120])})


def test_dcf_matches_constant_cashflow_perpetuity_and_equity_bridge():
    result = discounted_cash_flow(100, [0, 0, 0], .1, 0, 20, 50, 10)
    assert result.enterprise_value == pytest.approx(1_000)
    assert result.equity_value == pytest.approx(970)
    assert result.value_per_share == pytest.approx(97)


@pytest.mark.parametrize("changes", [
    {"shares": np.nan}, {"cash": np.inf}, {"base_fcff": np.nan},
    {"growth_rates": [0, -1]}, {"wacc": np.nan}, {"terminal_growth": -1},
])
def test_dcf_rejects_nonfinite_or_impossible_inputs(changes):
    arguments = dict(base_fcff=100, growth_rates=[.05, .05], wacc=.1,
                     terminal_growth=.02, cash=0, debt=0, shares=10)
    arguments.update(changes)
    with pytest.raises(ValueError):
        discounted_cash_flow(**arguments)


def test_invalid_sensitivity_combinations_are_unavailable_without_failing_valid_dcf():
    result = discounted_cash_flow(100, [0, 0], .02, .019, 0, 0, 10)
    assert result.enterprise_value > 0
    assert result.sensitivity.isna().any().any()
    for rate in result.sensitivity.index:
        for growth in result.sensitivity.columns:
            if rate <= growth:
                assert pd.isna(result.sensitivity.loc[rate, growth])


def test_comparable_valuation_excludes_infinite_peer_multiples():
    peers = pd.DataFrame({"EV/Revenue": [np.inf, 2], "EV/EBITDA": [np.inf, 10], "P/E": [np.inf, 15]})
    result = comparable_valuation(peers, 100, 20, 10, 0, 0, 10)
    assert np.isfinite(result.select_dtypes(include="number")).all().all()
    assert result.query("Method == 'P/E'")["Implied value per share"].tolist() == [15, 15, 15]


def test_roic_uses_average_capital_and_preserves_unknown_statement_inputs():
    frame = pd.DataFrame({
        "Year": [2023, 2024, 2025], "EBIT": [100, 100, 100],
        "Short-Term Debt": [100, 100, 100], "Long-Term Debt": [100, 100, 100],
        "Shareholders Equity": [700, 900, 1100], "Cash": [100, 100, np.nan],
        "Capital Expenditure": [20, 20, np.nan], "Depreciation": [5, 5, 5],
        "Total Current Assets": [200, 220, 240], "Total Current Liabilities": [100, 100, 100],
    })
    result = roic_reinvestment(frame, .25).set_index("Year")
    assert result.loc[2024, "ROIC"] == pytest.approx(75 / 900)
    assert result.loc[2024, "Reinvestment"] == 35
    assert np.isnan(result.loc[2025, "ROIC"])
    assert np.isnan(result.loc[2025, "Reinvestment"])


def test_roic_reinvestment_excludes_cash_and_current_borrowing_changes():
    frame = pd.DataFrame({
        "Year": [2023, 2024], "EBIT": [100, 100], "Short-Term Debt": [100, 200],
        "Long-Term Debt": [100, 100], "Shareholders Equity": [700, 700],
        "Cash": [100, 200], "Capital Expenditure": [20, 20], "Depreciation": [5, 5],
        "Total Current Assets": [300, 400], "Total Current Liabilities": [200, 300],
    })
    result = roic_reinvestment(frame, .25).set_index("Year")
    assert result.loc[2024, "Operating Working Capital"] == 100
    assert result.loc[2024, "Reinvestment"] == 15


def test_credit_missing_calendar_months_lower_average_and_withhold_proposal():
    frame = pd.DataFrame({"Date": ["01/01/2025", "01/03/2025", "01/05/2025"],
                          "Amount": [100_000, 100_000, 100_000]})
    result = credit(frame)
    assert result.monthly_cashflow["Transactions"].tolist() == [1, 0, 1, 0, 1]
    assert result.profile["Average Monthly Inflows"] == 60_000
    assert result.profile["Observed Months"] == 3
    assert result.profile["Missing Months"] == 2
    assert result.score is None
    assert result.proposal["Recommended Amount"] == 0
    assert any(reason.startswith("CG-E02") for reason in result.reasons)


def test_credit_missing_balances_are_missing_evidence_not_negative_balances():
    frame = pd.DataFrame({"Date": ["2025-01-01", "2025-02-01", "2025-03-01"],
                          "Amount": [100_000, 100_000, 100_000]})
    result = credit(frame)
    assert result.components.set_index("Component").loc["Balance resilience", "Points"] == 0
    assert any(reason.startswith("CG-L02") for reason in result.reasons)
    assert not any(reason.startswith("CG-L01") for reason in result.reasons)


def test_credit_financing_inflows_are_not_counted_as_business_repayment_capacity():
    rows = []
    for date in pd.date_range("2025-01-01", periods=3, freq="MS"):
        rows.extend([
            {"Date": date, "Amount": 100_000, "Category": "Business revenue"},
            {"Date": date, "Amount": 900_000, "Category": "Loan proceeds"},
            {"Date": date, "Amount": 200_000, "Category": "Owner transfer"},
            {"Date": date, "Amount": -60_000, "Category": "Inventory"},
        ])
    result = credit(pd.DataFrame(rows))
    assert result.profile["Average Monthly Inflows"] == 100_000
    assert result.profile["Average Net Cash Flow"] == 40_000
    assert result.profile["Excluded Nonbusiness Inflows"] == 3_300_000
    assert any(reason.startswith("CG-R05") for reason in result.reasons)


def test_credit_debt_repayment_is_counted_once_and_observed_service_is_a_floor():
    rows = []
    for date in pd.date_range("2025-01-01", periods=3, freq="MS"):
        rows.extend([
            {"Date": date, "Amount": 100_000, "Category": "Business revenue"},
            {"Date": date, "Amount": -60_000, "Category": "Inventory"},
            {"Date": date, "Amount": -10_000, "Category": "Debt service"},
        ])
    result = credit(pd.DataFrame(rows), existing_monthly_debt=5_000)
    assert result.profile["Average Monthly Outflows"] == 60_000
    assert result.profile["Effective Monthly Debt Service"] == 10_000
    assert result.proposal["Maximum New Monthly Payment"] == pytest.approx(40_000 / 1.2 - 10_000)
    assert any(reason.startswith("CG-A02") for reason in result.reasons)


@pytest.mark.parametrize("changes", [
    {"requested_amount": np.nan}, {"tenure_months": 12.5},
    {"risk_free_rate": np.inf}, {"reviewed_monthly_expenses": np.nan},
])
def test_credit_invalid_assumptions_are_rejected(changes):
    frame = pd.DataFrame({"Date": ["2025-01-01", "2025-02-01", "2025-03-01"],
                          "Amount": [100_000, 100_000, 100_000]})
    with pytest.raises(ValueError):
        credit(frame, **changes)


@pytest.mark.parametrize("date,amount", [("not a date", 100), ("2025-02-01", np.inf),
                                         ("2025-02-01", "not a number")])
def test_credit_does_not_silently_drop_invalid_transaction_rows(date, amount):
    frame = pd.DataFrame({"Date": ["2025-01-01", date, "2025-03-01"],
                          "Amount": [100_000, amount, 100_000]})
    with pytest.raises(ValueError, match="Every transaction"):
        credit(frame)


def test_exchange_comparison_handles_empty_company_and_excludes_infinite_values():
    frame = pd.DataFrame({"Year": [2025, 2025], "Exchange metric": ["Basic EPS", "NAV per Share"],
                          "Value": [5, np.inf]})
    result = exchange_metric_comparison({"AAA": frame, "BBB": pd.DataFrame()})
    assert result.loc["AAA", "Basic EPS"] == 5
    assert pd.isna(result.loc["AAA", "NAV per Share"])
    assert pd.isna(result.loc["BBB", "Basic EPS"])
    leaders = comparison_strengths(pd.DataFrame({"EPS": [5, np.inf]}, index=["AAA", "BBB"]), ["EPS"])
    assert leaders.iloc[0]["Reference leader"] == "AAA"


def test_duplicate_company_metric_requires_review():
    frame = pd.DataFrame({"Year": [2025, 2025], "Exchange metric": ["Basic EPS", "Basic EPS"],
                          "Value": [5, 6]})
    with pytest.raises(ValueError, match="duplicate"):
        exchange_metric_comparison({"AAA": frame})


def test_dupont_follows_fiscal_order_even_when_input_is_unsorted():
    frame = demo_company().iloc[::-1].copy()
    ratios, _ = calculate(frame)
    result = dupont(frame, ratios)
    assert result["DuPont ROE"].tolist() == pytest.approx(ratios["ROE"].tolist())


def test_validated_numeric_text_years_become_numeric_fiscal_index():
    frame = demo_company()
    frame["Year"] = frame["Year"].astype(str)
    result = analyze(frame)
    assert pd.api.types.is_integer_dtype(result.statements.index.dtype)
