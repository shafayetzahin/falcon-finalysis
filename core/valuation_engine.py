"""Transparent public-company valuation helpers for reviewed inputs."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class WACCResult:
    cost_of_equity: float
    after_tax_cost_of_debt: float
    equity_weight: float
    debt_weight: float
    wacc: float


@dataclass(frozen=True)
class DCFResult:
    forecast: pd.DataFrame
    enterprise_value: float
    equity_value: float
    value_per_share: float
    terminal_value_share: float
    sensitivity: pd.DataFrame


def calculate_wacc(market_cap: float, debt: float, risk_free_rate: float,
                   equity_risk_premium: float, beta: float,
                   pre_tax_cost_of_debt: float, tax_rate: float) -> WACCResult:
    values = [market_cap, debt, risk_free_rate, equity_risk_premium, beta,
              pre_tax_cost_of_debt, tax_rate]
    if not all(np.isfinite(values)):
        raise ValueError("WACC inputs must be finite numbers.")
    if market_cap <= 0 or debt < 0 or beta < 0:
        raise ValueError("Market capitalization must be positive; debt and beta cannot be negative.")
    if not 0 <= tax_rate < 1 or min(risk_free_rate, equity_risk_premium,
                                    pre_tax_cost_of_debt) < 0:
        raise ValueError("Rates must be nonnegative and tax must be below 100%.")
    capital = market_cap + debt
    equity_weight = market_cap / capital
    debt_weight = debt / capital
    cost_of_equity = risk_free_rate + beta * equity_risk_premium
    after_tax_debt = pre_tax_cost_of_debt * (1 - tax_rate)
    wacc = equity_weight * cost_of_equity + debt_weight * after_tax_debt
    return WACCResult(cost_of_equity, after_tax_debt, equity_weight, debt_weight, wacc)


def _dcf_value(base_fcff: float, growth_rates: list[float], wacc: float,
               terminal_growth: float) -> tuple[pd.DataFrame, float, float]:
    if base_fcff <= 0:
        raise ValueError("Base FCFF must be greater than zero.")
    if not growth_rates:
        raise ValueError("Provide at least one forecast growth rate.")
    if wacc <= terminal_growth:
        raise ValueError("WACC must be higher than terminal growth.")
    rows, fcff = [], float(base_fcff)
    for year, growth in enumerate(growth_rates, 1):
        fcff *= 1 + float(growth)
        discount_factor = (1 + wacc) ** year
        rows.append({"Forecast Year": year, "Growth": float(growth), "FCFF": fcff,
                     "Discount Factor": discount_factor, "PV of FCFF": fcff / discount_factor})
    terminal_value = fcff * (1 + terminal_growth) / (wacc - terminal_growth)
    terminal_pv = terminal_value / (1 + wacc) ** len(growth_rates)
    forecast = pd.DataFrame(rows)
    enterprise_value = float(forecast["PV of FCFF"].sum() + terminal_pv)
    return forecast, enterprise_value, float(terminal_pv)


def discounted_cash_flow(base_fcff: float, growth_rates: list[float], wacc: float,
                         terminal_growth: float, cash: float, debt: float,
                         shares: float) -> DCFResult:
    if shares <= 0:
        raise ValueError("Shares outstanding must be greater than zero.")
    if cash < 0 or debt < 0:
        raise ValueError("Cash and debt cannot be negative.")
    forecast, enterprise_value, terminal_pv = _dcf_value(
        base_fcff, growth_rates, wacc, terminal_growth)
    equity_value = enterprise_value + cash - debt
    value_per_share = equity_value / shares
    wacc_range = np.linspace(max(wacc - .02, terminal_growth + .005), wacc + .02, 5)
    growth_range = np.linspace(max(0.0, terminal_growth - .02),
                               min(terminal_growth + .02, wacc_range.min() - .005), 5)
    values = []
    for rate in wacc_range:
        row = []
        for growth in growth_range:
            _, ev, _ = _dcf_value(base_fcff, growth_rates, float(rate), float(growth))
            row.append((ev + cash - debt) / shares)
        values.append(row)
    sensitivity = pd.DataFrame(values,
                               index=pd.Index(wacc_range, name="WACC"),
                               columns=pd.Index(growth_range, name="Terminal growth"))
    return DCFResult(forecast, enterprise_value, equity_value, value_per_share,
                     terminal_pv / enterprise_value if enterprise_value else np.nan,
                     sensitivity)


def comparable_valuation(peers: pd.DataFrame, revenue: float, ebitda: float,
                         net_income: float, debt: float, cash: float,
                         shares: float) -> pd.DataFrame:
    """Apply peer low/median/high multiples to reviewed target denominators."""
    required = ["EV/Revenue", "EV/EBITDA", "P/E"]
    if not set(required).issubset(peers):
        raise ValueError("Peer table requires EV/Revenue, EV/EBITDA and P/E columns.")
    if shares <= 0:
        raise ValueError("Shares outstanding must be greater than zero.")
    clean = peers[required].apply(pd.to_numeric, errors="coerce")
    rows = []
    for metric, denominator, enterprise_based in [
        ("EV/Revenue", revenue, True), ("EV/EBITDA", ebitda, True), ("P/E", net_income, False)
    ]:
        values = clean[metric].dropna()
        values = values[values > 0]
        if values.empty or denominator <= 0:
            continue
        for label, multiple in [("Low", values.quantile(.25)),
                                ("Median", values.median()),
                                ("High", values.quantile(.75))]:
            headline_value = float(denominator * multiple)
            equity_value = headline_value + cash - debt if enterprise_based else headline_value
            rows.append({"Method": metric, "Case": label, "Selected multiple": float(multiple),
                         "Implied equity value": equity_value,
                         "Implied value per share": equity_value / shares})
    return pd.DataFrame(rows)


def roic_reinvestment(frame: pd.DataFrame, tax_rate: float) -> pd.DataFrame:
    """Calculate screening ROIC, reinvestment and intrinsic-growth history."""
    data = frame.copy().sort_values("Year")

    def numeric(name: str) -> pd.Series:
        values = data[name] if name in data else pd.Series(np.nan, index=data.index)
        return pd.to_numeric(values, errors="coerce")

    ebit = numeric("EBIT")
    debt = numeric("Short-Term Debt").fillna(0) + numeric("Long-Term Debt").fillna(0)
    equity = numeric("Shareholders Equity")
    cash = numeric("Cash").fillna(0)
    invested = debt + equity - cash
    nopat = ebit * (1 - tax_rate)
    capex = numeric("Capital Expenditure").fillna(0)
    depreciation = numeric("Depreciation").fillna(0)
    working_capital = (numeric("Total Current Assets") - numeric("Total Current Liabilities"))
    reinvestment = capex - depreciation + working_capital.diff()
    rate = reinvestment / nopat.replace(0, np.nan)
    roic = nopat / invested.replace(0, np.nan)
    return pd.DataFrame({"Year": data["Year"].astype(int), "NOPAT": nopat,
                         "Invested Capital": invested, "ROIC": roic,
                         "Reinvestment": reinvestment, "Reinvestment Rate": rate,
                         "Intrinsic Growth": roic * rate})
