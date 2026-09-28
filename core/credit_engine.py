"""Transparent small-business cash-flow credit decision support."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


TRANSACTION_COLUMNS = ["Date", "Description", "Amount", "Balance", "Category", "Source"]
CREDIT_MODEL_VERSION = "CG-CF-1.1"


@dataclass(frozen=True)
class CreditAnalysis:
    monthly_cashflow: pd.DataFrame
    components: pd.DataFrame
    score: float | None
    band: str
    confidence: float
    reasons: list[str]
    profile: dict[str, float]
    proposal: dict[str, float | str]


def _bounded(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def _transactions(frame: pd.DataFrame) -> pd.DataFrame:
    if not {"Date", "Amount"}.issubset(frame.columns):
        raise ValueError("Transactions require Date and Amount columns.")
    out = frame.copy().reindex(columns=TRANSACTION_COLUMNS)
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out["Amount"] = pd.to_numeric(out["Amount"], errors="coerce")
    out["Balance"] = pd.to_numeric(out["Balance"], errors="coerce")
    out = out.dropna(subset=["Date", "Amount"]).sort_values("Date").reset_index(drop=True)
    if out.empty:
        raise ValueError("No valid dated transactions were found.")
    if not (out["Amount"] > 0).any():
        raise ValueError("At least one positive business inflow is required.")
    return out


def _payment(principal: float, annual_rate: float, months: int) -> float:
    if principal <= 0 or months <= 0:
        return 0.0
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return principal / months
    return principal * monthly_rate / (1 - (1 + monthly_rate) ** -months)


def _present_value(payment: float, annual_rate: float, months: int) -> float:
    monthly_rate = annual_rate / 12
    if payment <= 0:
        return 0.0
    if monthly_rate == 0:
        return payment * months
    return payment * (1 - (1 + monthly_rate) ** -months) / monthly_rate


def analyze_credit(transactions: pd.DataFrame, requested_amount: float, tenure_months: int,
                   existing_monthly_debt: float, minimum_dscr: float,
                   risk_free_rate: float, operating_premium: float,
                   liquidity_premium: float, risk_premium: float,
                   document_coverage: float = 0.0,
                   reviewed_monthly_expenses: float | None = None) -> CreditAnalysis:
    """Profile verified cash flow and produce a capped, benchmark-linked loan proposal."""
    if requested_amount <= 0:
        raise ValueError("Requested amount must be greater than zero.")
    if not 1 <= int(tenure_months) <= 60:
        raise ValueError("Tenure must be between 1 and 60 months.")
    if existing_monthly_debt < 0:
        raise ValueError("Existing monthly debt service cannot be negative.")
    if minimum_dscr < 1:
        raise ValueError("Minimum DSCR must be at least 1.00x.")
    rates = [risk_free_rate, operating_premium, liquidity_premium, risk_premium]
    if any(rate < 0 for rate in rates):
        raise ValueError("Benchmark and pricing premiums cannot be negative.")
    if operating_premium + liquidity_premium + risk_premium <= 0:
        raise ValueError("At least one pricing premium is required so the proposed rate exceeds the benchmark.")
    document_coverage = _bounded(document_coverage)
    clean = _transactions(transactions)

    clean["Month"] = clean["Date"].dt.to_period("M").dt.to_timestamp()
    monthly = clean.groupby("Month").agg(
        Inflows=("Amount", lambda values: values[values > 0].sum()),
        Outflows=("Amount", lambda values: -values[values < 0].sum()),
        Transactions=("Amount", "size"),
    )
    monthly["Net Cash Flow"] = monthly["Inflows"] - monthly["Outflows"]
    monthly["Net Margin"] = monthly["Net Cash Flow"].div(monthly["Inflows"].replace(0, np.nan))
    months = len(monthly)
    average_inflows = float(monthly["Inflows"].mean())
    derived_expenses = float(monthly["Outflows"].mean())
    monthly_expenses = (derived_expenses if reviewed_monthly_expenses is None
                        else float(reviewed_monthly_expenses))
    if monthly_expenses < 0:
        raise ValueError("Reviewed monthly operating expenses cannot be negative.")
    average_net = average_inflows - monthly_expenses
    revenue_cv = (float(monthly["Inflows"].std(ddof=0) / average_inflows)
                  if average_inflows > 0 else np.nan)
    positive_month_share = float((monthly["Net Cash Flow"] > 0).mean())
    observed_balances = clean["Balance"].dropna()
    nonnegative_balance_share = (float((observed_balances >= 0).mean())
                                 if len(observed_balances) else .5)
    net_margin = average_net / average_inflows if average_inflows else 0.0
    inflows = clean[clean["Amount"] > 0]
    grouped_inflows = inflows.groupby(
        inflows["Description"].fillna("").astype(str).str.lower().str.strip())["Amount"].sum()
    inflow_concentration = (float(grouped_inflows.max() / grouped_inflows.sum())
                            if not grouped_inflows.empty and grouped_inflows.sum() else 0.0)
    returned_payment_count = int(clean["Description"].fillna("").astype(str).str.contains(
        r"return|reversal|bounce|dishonou?r|failed", case=False, regex=True).sum())

    component_rows = [
        ("Evidence history", 15.0, _bounded(months / 12), f"{months} observed month(s)"),
        ("Revenue stability", 20.0, _bounded(1 - revenue_cv), f"Revenue coefficient of variation {revenue_cv:.2f}"),
        ("Cash surplus", 25.0, _bounded(net_margin / .20), f"Reviewed average net margin {net_margin:.1%}"),
        ("Positive months", 20.0, positive_month_share, f"{positive_month_share:.0%} of months have positive observed net cash flow"),
        ("Balance resilience", 10.0, nonnegative_balance_share,
         "No balance column supplied" if not len(observed_balances) else f"{nonnegative_balance_share:.0%} of observed balances are nonnegative"),
        ("Document coverage", 10.0, document_coverage, f"{document_coverage:.0%} of requested document groups reviewed"),
    ]
    components = pd.DataFrame(component_rows, columns=["Component", "Weight", "Factor", "Evidence"])
    components["Points"] = components["Weight"] * components["Factor"]
    score = float(components["Points"].sum()) if months >= 3 else None
    if score is None:
        band = "Insufficient evidence"
    elif score >= 80:
        band = "Stronger cash-flow profile"
    elif score >= 65:
        band = "Moderate cash-flow profile"
    elif score >= 50:
        band = "Cautious cash-flow profile"
    else:
        band = "Weak cash-flow profile"
    confidence = _bounded(.7 * months / 12 + .3 * document_coverage)

    annual_rate = sum(rates)
    operating_surplus = max(average_inflows - monthly_expenses, 0.0)
    max_new_payment = max(operating_surplus / minimum_dscr - existing_monthly_debt, 0.0)
    capacity = _present_value(max_new_payment, annual_rate, int(tenure_months))
    recommended_amount = min(float(requested_amount), capacity) if score is not None else 0.0
    proposed_payment = _payment(recommended_amount, annual_rate, int(tenure_months))
    total_debt_service = existing_monthly_debt + proposed_payment
    post_loan_dscr = (operating_surplus / total_debt_service if total_debt_service > 0 else np.nan)

    reasons = []
    if months < 6:
        reasons.append("CG-E01 · Less than six months of transaction history")
    if revenue_cv > .35:
        reasons.append("CG-R01 · Monthly inflows are volatile")
    if positive_month_share < .75:
        reasons.append("CG-C01 · Fewer than 75% of observed months have positive net cash flow")
    if nonnegative_balance_share < .90:
        reasons.append("CG-L01 · Negative balances appear in the supplied history")
    if document_coverage < .75:
        reasons.append("CG-D01 · Requested document coverage is below 75%")
    if inflow_concentration > .50:
        reasons.append("CG-R02 · More than 50% of described inflows are concentrated in one label or channel")
    if returned_payment_count:
        reasons.append(f"CG-C02 · {returned_payment_count} returned, reversed or failed-payment reference(s) require review")
    if capacity < requested_amount:
        reasons.append("CG-A01 · Requested amount exceeds the modeled repayment capacity")
    if not reasons:
        reasons.append("CG-M01 · No policy concern triggered; complete human underwriting review")

    profile = {
        "Months": float(months), "Average Monthly Inflows": average_inflows,
        "Average Monthly Outflows": derived_expenses, "Reviewed Monthly Expenses": monthly_expenses,
        "Average Net Cash Flow": average_net, "Revenue CV": revenue_cv,
        "Positive Month Share": positive_month_share,
        "Nonnegative Balance Share": nonnegative_balance_share,
        "Largest Inflow Concentration": inflow_concentration,
        "Returned Payment References": float(returned_payment_count),
    }
    proposal = {
        "Requested Amount": float(requested_amount), "Capacity Amount": float(capacity),
        "Recommended Amount": float(recommended_amount), "Tenure Months": float(tenure_months),
        "Risk Free Rate": float(risk_free_rate), "Annual Proposed Rate": float(annual_rate),
        "Maximum New Monthly Payment": float(max_new_payment),
        "Proposed Monthly Payment": float(proposed_payment), "Post Loan DSCR": float(post_loan_dscr),
        "Model Version": CREDIT_MODEL_VERSION,
    }
    return CreditAnalysis(monthly.reset_index(), components, score, band, confidence,
                          reasons, profile, proposal)
