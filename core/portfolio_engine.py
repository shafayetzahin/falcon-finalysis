"""Portfolio return and risk calculations with explicit corporate actions."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


ACTION_COLUMNS = [
    "Date", "Ticker", "Cash Dividend per Share", "Cash Dividend %", "Face Value",
    "Stock Dividend %", "Rights New Shares", "Rights Held Shares", "Rights Price",
    "Split New Shares", "Split Old Shares", "Source",
]
FREQUENCIES = {
    "Daily": (None, 252),
    "Weekly": ("W-FRI", 52),
    "Monthly": ("ME", 12),
}
HOLDING_COLUMNS = ["Ticker", "Initial Shares", "Purchase Price", "Initial Fees", "Exit Fees"]


@dataclass(frozen=True)
class PortfolioAnalysis:
    asset_summary: pd.DataFrame
    periodic_returns: pd.DataFrame
    risk_summary: pd.DataFrame
    covariance: pd.DataFrame
    annualized_covariance: pd.DataFrame
    portfolio_returns: pd.Series
    portfolio_summary: dict[str, float]


def empty_actions() -> pd.DataFrame:
    return pd.DataFrame(columns=ACTION_COLUMNS)


def empty_holdings() -> pd.DataFrame:
    return pd.DataFrame(columns=HOLDING_COLUMNS)


def _holdings(frame: pd.DataFrame | None, tickers: list[str]) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame({"Ticker": tickers, "Initial Shares": 1.0,
                             "Purchase Price": np.nan, "Initial Fees": 0.0, "Exit Fees": 0.0})
    out = frame.copy().reindex(columns=HOLDING_COLUMNS)
    out["Ticker"] = out["Ticker"].astype("string").str.strip().str.upper()
    for column in HOLDING_COLUMNS[1:]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if out["Ticker"].duplicated().any():
        raise ValueError("Each ticker can appear only once in holdings.")
    if (out["Initial Shares"].fillna(0) <= 0).any():
        raise ValueError("Initial shares must be greater than zero.")
    if (out[["Initial Fees", "Exit Fees"]].fillna(0) < 0).any().any():
        raise ValueError("Transaction fees cannot be negative.")
    indexed = out.set_index("Ticker")
    rows = []
    for ticker in tickers:
        row = indexed.loc[ticker].to_dict() if ticker in indexed.index else {}
        initial_shares = row.get("Initial Shares", 1.0)
        initial_shares = 1.0 if pd.isna(initial_shares) else float(initial_shares)
        rows.append({"Ticker": ticker, "Initial Shares": initial_shares,
                     "Purchase Price": row.get("Purchase Price", np.nan),
                     "Initial Fees": float(row.get("Initial Fees", 0.0) or 0.0),
                     "Exit Fees": float(row.get("Exit Fees", 0.0) or 0.0)})
    return pd.DataFrame(rows)


def _actions(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return empty_actions()
    out = frame.copy().reindex(columns=ACTION_COLUMNS)
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out["Ticker"] = out["Ticker"].astype("string").str.strip().str.upper()
    numeric = [column for column in ACTION_COLUMNS if column not in {"Date", "Ticker", "Source"}]
    for column in numeric:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)
        if (out[column] < 0).any():
            raise ValueError(f"{column} cannot be negative.")
    return out.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)


def _prices(history: pd.DataFrame, ticker: str) -> pd.Series:
    if not {"Date", "Close"}.issubset(history.columns):
        raise ValueError(f"{ticker}: price history needs Date and Close columns.")
    frame = history.copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
    if "Ticker" in frame:
        frame = frame[frame["Ticker"].astype(str).str.upper().eq(ticker)]
    frame = frame.dropna(subset=["Date", "Close"])
    frame = frame[frame["Close"] > 0].sort_values("Date").drop_duplicates("Date", keep="last")
    if len(frame) < 2:
        raise ValueError(f"{ticker}: at least two positive closing prices are required.")
    return frame.set_index("Date")["Close"].astype(float)


def _asset_analysis(ticker: str, history: pd.DataFrame, actions: pd.DataFrame,
                    holding: pd.Series) -> tuple[dict, pd.Series]:
    prices = _prices(history, ticker)
    relevant = actions[(actions["Ticker"] == ticker)
                       & (actions["Date"] > prices.index[0])
                       & (actions["Date"] <= prices.index[-1])].copy()
    if not relevant.empty:
        positions = prices.index.searchsorted(relevant["Date"], side="left")
        relevant["Effective Date"] = [prices.index[min(position, len(prices) - 1)] for position in positions]

    initial_shares = float(holding["Initial Shares"])
    shares = initial_shares
    cash_total = 0.0
    rights_total = 0.0
    returns: list[float] = []
    return_dates: list[pd.Timestamp] = []
    for position in range(1, len(prices)):
        current_date = prices.index[position]
        prior_value = shares * float(prices.iloc[position - 1])
        cash_today = 0.0
        rights_today = 0.0
        if not relevant.empty:
            for _, action in relevant[relevant["Effective Date"] == current_date].iterrows():
                cash_per_share = float(action["Cash Dividend per Share"])
                if cash_per_share == 0 and action["Cash Dividend %"] > 0 and action["Face Value"] > 0:
                    cash_per_share = float(action["Cash Dividend %"] * action["Face Value"] / 100)
                cash_today += shares * cash_per_share
                shares *= 1 + float(action["Stock Dividend %"]) / 100
                held = float(action["Rights Held Shares"])
                new = float(action["Rights New Shares"])
                if held > 0 and new > 0:
                    new_shares = shares * new / held
                    rights_today += new_shares * float(action["Rights Price"])
                    shares += new_shares
                split_old = float(action["Split Old Shares"])
                split_new = float(action["Split New Shares"])
                if split_old > 0 and split_new > 0:
                    shares *= split_new / split_old
        ending_value = shares * float(prices.iloc[position])
        returns.append((ending_value + cash_today - rights_today - prior_value) / prior_value)
        return_dates.append(current_date)
        cash_total += cash_today
        rights_total += rights_today

    start_price, end_price = float(prices.iloc[0]), float(prices.iloc[-1])
    purchase_price = holding["Purchase Price"]
    purchase_price = start_price if pd.isna(purchase_price) or float(purchase_price) <= 0 else float(purchase_price)
    initial_fees = float(holding["Initial Fees"])
    exit_fees = float(holding["Exit Fees"])
    initial_cost = initial_shares * purchase_price + initial_fees
    invested = initial_cost + rights_total
    ending_value = shares * end_price - exit_fees
    capital_gain = ending_value - invested
    total_gain = capital_gain + cash_total
    summary = {
        "Ticker": ticker,
        "Start Date": prices.index[0].date(),
        "End Date": prices.index[-1].date(),
        "Start Close": start_price,
        "End Close": end_price,
        "Initial Shares": initial_shares,
        "Purchase Price": purchase_price,
        "Ending Shares": shares,
        "Initial Cost": initial_cost,
        "Current Value": ending_value,
        "Transaction Fees": initial_fees + exit_fees,
        "Cash Dividends": cash_total,
        "Rights Investment": rights_total,
        "Capital Gain": capital_gain,
        "Dividend Yield": cash_total / invested if invested else np.nan,
        "Capital Gain %": capital_gain / invested if invested else np.nan,
        "Total Return %": total_gain / invested if invested else np.nan,
        "Price Return %": end_price / start_price - 1,
    }
    return summary, pd.Series(returns, index=return_dates, name=ticker, dtype=float)


def _periodic(daily: pd.DataFrame, frequency: str) -> tuple[pd.DataFrame, int]:
    if frequency not in FREQUENCIES:
        raise ValueError("Return frequency must be Daily, Weekly or Monthly.")
    rule, annual_periods = FREQUENCIES[frequency]
    if rule:
        daily = daily.resample(rule).apply(lambda values: (1 + values.dropna()).prod() - 1)
    return daily.dropna(how="all"), annual_periods


def analyze_portfolio(price_history: dict[str, pd.DataFrame], actions: pd.DataFrame | None = None,
                      weights: dict[str, float] | None = None,
                      frequency: str = "Daily", holdings: pd.DataFrame | None = None,
                      risk_free_rate: float = 0.0) -> PortfolioAnalysis:
    """Calculate holding-period results and aligned periodic portfolio risk statistics."""
    if not price_history:
        raise ValueError("Add price history for at least one stock.")
    clean_actions = _actions(actions)
    normalized_tickers = [str(ticker).strip().upper() for ticker in price_history]
    clean_holdings = _holdings(holdings, normalized_tickers).set_index("Ticker")
    summaries, series = [], []
    for raw_ticker, history in price_history.items():
        ticker = str(raw_ticker).strip().upper()
        summary, asset_returns = _asset_analysis(ticker, history, clean_actions,
                                                 clean_holdings.loc[ticker])
        summaries.append(summary)
        series.append(asset_returns)
    daily = pd.concat(series, axis=1).sort_index()
    periodic, annual_periods = _periodic(daily, frequency)
    aligned = periodic.dropna()
    if len(aligned) < 2:
        raise ValueError("The selected stocks need at least two aligned return observations for risk statistics.")

    tickers = list(price_history)
    supplied = weights or {ticker: 1 for ticker in tickers}
    weight_values = pd.Series({ticker: float(supplied.get(ticker, 0)) for ticker in tickers})
    if (weight_values < 0).any() or weight_values.sum() <= 0:
        raise ValueError("Portfolio weights must be nonnegative and sum to more than zero.")
    weight_values /= weight_values.sum()

    covariance = aligned.cov()
    annual_covariance = covariance * annual_periods
    annual_returns = aligned.mean() * annual_periods
    annual_volatility = aligned.std(ddof=1) * np.sqrt(annual_periods)
    downside = aligned.clip(upper=0).pow(2).mean().pow(.5) * np.sqrt(annual_periods)
    wealth = (1 + aligned).cumprod()
    drawdown = wealth.div(wealth.cummax()).sub(1).min()
    risk = pd.DataFrame({
        "Average Return": aligned.mean(),
        "Standard Deviation": aligned.std(ddof=1),
        "Variance": aligned.var(ddof=1),
        "Annualized Average Return": annual_returns,
        "Annualized Volatility": annual_volatility,
        "Sharpe Ratio": (annual_returns - risk_free_rate) / annual_volatility.replace(0, np.nan),
        "Sortino Ratio": (annual_returns - risk_free_rate) / downside.replace(0, np.nan),
        "Maximum Drawdown": drawdown,
        "Weight": weight_values,
    }).rename_axis("Ticker").reset_index()
    portfolio_returns = aligned.mul(weight_values, axis=1).sum(axis=1).rename("Portfolio")
    portfolio_annual_return = float(portfolio_returns.mean() * annual_periods)
    portfolio_volatility = float(portfolio_returns.std(ddof=1) * np.sqrt(annual_periods))
    portfolio_downside = float(portfolio_returns.clip(upper=0).pow(2).mean() ** .5 * np.sqrt(annual_periods))
    portfolio_wealth = (1 + portfolio_returns).cumprod()
    maximum_drawdown = float(portfolio_wealth.div(portfolio_wealth.cummax()).sub(1).min())
    historical_var = float(max(0.0, -portfolio_returns.quantile(.05)))
    asset_summary = pd.DataFrame(summaries)
    portfolio_summary = {
        "Average Return": float(portfolio_returns.mean()),
        "Standard Deviation": float(portfolio_returns.std(ddof=1)),
        "Variance": float(portfolio_returns.var(ddof=1)),
        "Annualized Average Return": portfolio_annual_return,
        "Annualized Volatility": portfolio_volatility,
        "Sharpe Ratio": ((portfolio_annual_return - risk_free_rate) / portfolio_volatility
                         if portfolio_volatility else np.nan),
        "Sortino Ratio": ((portfolio_annual_return - risk_free_rate) / portfolio_downside
                          if portfolio_downside else np.nan),
        "Maximum Drawdown": maximum_drawdown,
        "Historical VaR 95%": historical_var,
        "Total Invested": float(asset_summary["Initial Cost"].sum() + asset_summary["Rights Investment"].sum()),
        "Current Value": float(asset_summary["Current Value"].sum()),
        "Total Cash Dividends": float(asset_summary["Cash Dividends"].sum()),
        "Total Gain": float(asset_summary["Capital Gain"].sum() + asset_summary["Cash Dividends"].sum()),
        "Risk Free Rate": float(risk_free_rate),
        "Observations": float(len(aligned)),
    }
    return PortfolioAnalysis(asset_summary, aligned, risk, covariance,
                             annual_covariance, portfolio_returns, portfolio_summary)


def portfolio_risk_contribution(analysis: PortfolioAnalysis) -> pd.DataFrame:
    """Decompose portfolio volatility by asset using the analyzed weights."""
    tickers = list(analysis.annualized_covariance.columns)
    weights = analysis.risk_summary.set_index("Ticker")["Weight"].reindex(tickers).astype(float)
    covariance = analysis.annualized_covariance.loc[tickers, tickers]
    variance = float(weights.to_numpy() @ covariance.to_numpy() @ weights.to_numpy())
    volatility = float(np.sqrt(max(variance, 0.0)))
    marginal = covariance.to_numpy() @ weights.to_numpy()
    component = weights.to_numpy() * marginal / volatility if volatility else np.zeros(len(tickers))
    share = component / component.sum() if component.sum() else np.zeros(len(tickers))
    return pd.DataFrame({"Ticker": tickers, "Weight": weights.to_numpy(),
                         "Volatility contribution": component,
                         "Share of portfolio risk": share})


def efficient_frontier(analysis: PortfolioAnalysis, risk_free_rate: float = 0.0,
                       simulations: int = 2500) -> pd.DataFrame:
    """Create a deterministic long-only opportunity set from analyzed return history."""
    tickers = list(analysis.annualized_covariance.columns)
    annual_returns = analysis.risk_summary.set_index("Ticker").loc[
        tickers, "Annualized Average Return"].to_numpy(float)
    covariance = analysis.annualized_covariance.loc[tickers, tickers].to_numpy(float)
    rng = np.random.default_rng(42)
    weights = rng.dirichlet(np.ones(len(tickers)), size=max(int(simulations), 100))
    returns = weights @ annual_returns
    volatility = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", weights, covariance, weights), 0))
    sharpe = np.divide(returns - risk_free_rate, volatility,
                       out=np.full_like(returns, np.nan), where=volatility > 0)
    result = pd.DataFrame({"Annualized Return": returns, "Annualized Volatility": volatility,
                           "Sharpe Ratio": sharpe})
    for position, ticker in enumerate(tickers):
        result[f"Weight · {ticker}"] = weights[:, position]
    return result.sort_values("Annualized Volatility").reset_index(drop=True)


def rebalance_plan(current_values: dict[str, float], target_weights: dict[str, float]) -> pd.DataFrame:
    """Calculate reviewable buy/sell amounts for a long-only target allocation."""
    current = pd.Series({str(key).upper(): float(value) for key, value in current_values.items()})
    target = pd.Series({str(key).upper(): float(value) for key, value in target_weights.items()})
    if (current < 0).any() or current.sum() <= 0:
        raise ValueError("Current portfolio values must be nonnegative and sum to more than zero.")
    if (target < 0).any() or target.sum() <= 0:
        raise ValueError("Target weights must be nonnegative and sum to more than zero.")
    tickers = sorted(set(current.index) | set(target.index))
    current = current.reindex(tickers, fill_value=0.0)
    target = target.reindex(tickers, fill_value=0.0) / target.sum()
    total = float(current.sum())
    target_value = target * total
    trade = target_value - current
    return pd.DataFrame({"Ticker": tickers, "Current value": current.values,
                         "Current weight": (current / total).values,
                         "Target weight": target.values, "Target value": target_value.values,
                         "Indicative trade": trade.values,
                         "Action": np.where(trade > .01, "BUY", np.where(trade < -.01, "SELL", "HOLD"))})
