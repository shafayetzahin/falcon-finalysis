"""Transparent small-business cash-flow credit decision support."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


TRANSACTION_COLUMNS = ["Date", "Description", "Amount", "Balance", "Category", "Source"]
CREDIT_MODEL_VERSION = "CG-CF-1.2"


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
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce", format="mixed", dayfirst=True)
    out["Amount"] = pd.to_numeric(out["Amount"], errors="coerce")
    original_balances = out["Balance"]
    out["Balance"] = pd.to_numeric(original_balances, errors="coerce")
    if out["Date"].isna().any() or not np.isfinite(out["Amount"]).all():
        raise ValueError("Every transaction needs a valid date and a finite amount; correct invalid rows before analysis.")
    if (original_balances.notna() & ~np.isfinite(out["Balance"])).any():
        raise ValueError("Balances must be finite numbers or blank cells.")
    out = out.sort_values("Date").reset_index(drop=True)
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
    numbers = [requested_amount, tenure_months, existing_monthly_debt, minimum_dscr,
               risk_free_rate, operating_premium, liquidity_premium, risk_premium, document_coverage]
    if reviewed_monthly_expenses is not None:
        numbers.append(reviewed_monthly_expenses)
    if not all(np.isfinite(numbers)):
        raise ValueError("Credit assumptions must be finite numbers.")
    if requested_amount <= 0:
        raise ValueError("Requested amount must be greater than zero.")
    if tenure_months != int(tenure_months) or not 1 <= tenure_months <= 60:
        raise ValueError("Tenure must be a whole number between 1 and 60 months.")
    if existing_monthly_debt < 0:
        raise ValueError("Existing monthly debt service cannot be negative.")
    if minimum_dscr < 1:
        raise ValueError("Minimum DSCR must be at least 1.00x.")
    rates = [risk_free_rate, operating_premium, liquidity_premium, risk_premium]
    if any(rate < 0 for rate in rates):
        raise ValueError("Benchmark and pricing premiums cannot be negative.")
    if operating_premium + liquidity_premium + risk_premium <= 0:
        raise ValueError("At least one pricing premium is required so the proposed rate exceeds the benchmark.")
    if not 0 <= document_coverage <= 1:
        raise ValueError("Document coverage must be between 0% and 100%.")
    clean = _transactions(transactions)

    categories = clean["Category"].fillna("").astype(str).str.strip().str.lower()
    nonoperating = categories.str.contains(
        r"loan|debt|borrow|financ|transfer|owner|capital contribution|personal|gift|salary|refund|reversal|returned payment",
        regex=True)
    debt_service = (clean["Amount"] < 0) & categories.str.contains(
        r"debt service|loan repayment|emi|installment|instalment", regex=True)
    clean["Business Inflow"] = clean["Amount"].where((clean["Amount"] > 0) & ~nonoperating, 0.0)
    clean["Excluded Inflow"] = clean["Amount"].where((clean["Amount"] > 0) & nonoperating, 0.0)
    clean["Operating Outflow"] = -clean["Amount"].where((clean["Amount"] < 0) & ~debt_service, 0.0)
    clean["Debt Service"] = -clean["Amount"].where(debt_service, 0.0)
    if not (clean["Business Inflow"] > 0).any():
        raise ValueError("No business inflows remain after excluding reviewed financing and transfer categories.")
    clean["Month"] = clean["Date"].dt.to_period("M").dt.to_timestamp()
    monthly = clean.groupby("Month").agg(
        Inflows=("Business Inflow", "sum"),
        Outflows=("Amount", lambda values: -values[values < 0].sum()),
        **{"Operating Outflows": ("Operating Outflow", "sum"),
           "Debt Service": ("Debt Service", "sum"),
           "Excluded Inflows": ("Excluded Inflow", "sum")},
        Transactions=("Amount", "size"),
    )
    observed_months = len(monthly)
    complete_months = pd.date_range(monthly.index.min(), monthly.index.max(), freq="MS")
    monthly = monthly.reindex(complete_months, fill_value=0).rename_axis("Month")
    missing_months = len(monthly) - observed_months
    if not np.isfinite(monthly.to_numpy()).all():
        raise ValueError("Monthly cash-flow totals exceed the supported numeric range.")
    monthly["Net Cash Flow"] = monthly["Inflows"] - monthly["Outflows"]
    monthly["Net Margin"] = monthly["Net Cash Flow"].div(monthly["Inflows"].replace(0, np.nan))
    months = len(monthly)
    average_inflows = float(monthly["Inflows"].mean())
    derived_expenses = float(monthly["Operating Outflows"].mean())
    observed_debt_service = float(monthly["Debt Service"].mean())
    effective_debt_service = max(existing_monthly_debt, observed_debt_service)
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
                                 if len(observed_balances) else np.nan)
    net_margin = average_net / average_inflows if average_inflows else 0.0
    inflows = clean[clean["Business Inflow"] > 0]
    descriptions = inflows["Description"].fillna("").astype(str).str.lower().str.strip()
    grouped_inflows = inflows.loc[descriptions.ne("")].groupby(descriptions[descriptions.ne("")])["Amount"].sum()
    inflow_concentration = (float(grouped_inflows.max() / grouped_inflows.sum())
                            if not grouped_inflows.empty and grouped_inflows.sum() else 0.0)
    returned_payment_count = int(clean["Description"].fillna("").astype(str).str.contains(
        r"return|reversal|bounce|dishonou?r|failed", case=False, regex=True).sum())

    component_rows = [
        ("Evidence history", 15.0, _bounded(observed_months / 12),
         f"{observed_months} observed month(s) across {months} calendar month(s)"),
        ("Revenue stability", 20.0, _bounded(1 - revenue_cv), f"Revenue coefficient of variation {revenue_cv:.2f}"),
        ("Cash surplus", 25.0, _bounded(net_margin / .20), f"Reviewed average net margin {net_margin:.1%}"),
        ("Positive months", 20.0, positive_month_share, f"{positive_month_share:.0%} of months have positive observed net cash flow"),
        ("Balance resilience", 10.0, nonnegative_balance_share if len(observed_balances) else 0.0,
         "No balance column supplied" if not len(observed_balances) else f"{nonnegative_balance_share:.0%} of observed balances are nonnegative"),
        ("Document coverage", 10.0, document_coverage, f"{document_coverage:.0%} of requested document groups reviewed"),
    ]
    components = pd.DataFrame(component_rows, columns=["Component", "Weight", "Factor", "Evidence"])
    components["Points"] = components["Weight"] * components["Factor"]
    # An internal month with no rows may indicate either no activity or an omitted
    # statement. Withhold a lending score until continuous evidence is supplied.
    score = float(components["Points"].sum()) if observed_months >= 3 and not missing_months else None
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
    confidence = _bounded(.7 * observed_months / 12 + .3 * document_coverage)
    confidence *= observed_months / months

    annual_rate = sum(rates)
    if not np.isfinite(annual_rate):
        raise ValueError("Combined loan rate exceeds the supported numeric range.")
    operating_surplus = max(average_inflows - monthly_expenses, 0.0)
    max_new_payment = max(operating_surplus / minimum_dscr - effective_debt_service, 0.0)
    capacity = _present_value(max_new_payment, annual_rate, int(tenure_months))
    recommended_amount = min(float(requested_amount), capacity) if score is not None else 0.0
    proposed_payment = _payment(recommended_amount, annual_rate, int(tenure_months))
    total_debt_service = effective_debt_service + proposed_payment
    post_loan_dscr = (operating_surplus / total_debt_service if total_debt_service > 0 else np.nan)

    reasons = []
    if missing_months:
        reasons.append(f"CG-E02 · {missing_months} calendar month(s) have no transactions; confirm complete statement coverage before scoring")
    if months < 6:
        reasons.append("CG-E01 · Less than six months of transaction history")
    if revenue_cv > .35:
        reasons.append("CG-R01 · Monthly inflows are volatile")
    if positive_month_share < .75:
        reasons.append("CG-C01 · Fewer than 75% of observed months have positive net cash flow")
    if not len(observed_balances):
        reasons.append("CG-L02 · Balance history is unavailable; balance resilience has no supporting evidence")
    elif nonnegative_balance_share < .90:
        reasons.append("CG-L01 · Negative balances appear in the supplied history")
    if document_coverage < .75:
        reasons.append("CG-D01 · Requested document coverage is below 75%")
    if inflow_concentration > .50:
        reasons.append("CG-R02 · More than 50% of described inflows are concentrated in one label or channel")
    if descriptions.eq("").any():
        reasons.append("CG-R03 · Some inflows lack descriptions; source concentration requires review")
    unknown_inflows = (clean["Business Inflow"] > 0) & ~categories.eq("business revenue")
    if unknown_inflows.any():
        reasons.append("CG-R04 · Some counted inflows lack a reviewed Business revenue category; cash receipts are not verified revenue")
    excluded_inflows = float(clean["Excluded Inflow"].sum())
    if excluded_inflows:
        reasons.append("CG-R05 · Reviewed financing, personal or transfer inflows are excluded from repayment capacity")
    if observed_debt_service > existing_monthly_debt:
        reasons.append("CG-A02 · Observed average debt repayments exceed declared debt service; capacity uses the higher obligation")
    if returned_payment_count:
        reasons.append(f"CG-C02 · {returned_payment_count} returned, reversed or failed-payment reference(s) require review")
    if capacity < requested_amount:
        reasons.append("CG-A01 · Requested amount exceeds the modeled repayment capacity")
    if not reasons:
        reasons.append("CG-M01 · No policy concern triggered; complete human underwriting review")

    profile = {
        "Months": float(months), "Observed Months": float(observed_months),
        "Missing Months": float(missing_months), "Average Monthly Inflows": average_inflows,
        "Average Monthly Outflows": derived_expenses, "Reviewed Monthly Expenses": monthly_expenses,
        "Observed Monthly Debt Service": observed_debt_service,
        "Effective Monthly Debt Service": float(effective_debt_service),
        "Excluded Nonbusiness Inflows": excluded_inflows,
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
        "Existing Monthly Debt Service": float(effective_debt_service),
        "Proposed Monthly Payment": float(proposed_payment), "Post Loan DSCR": float(post_loan_dscr),
        "Model Version": CREDIT_MODEL_VERSION,
    }
    return CreditAnalysis(monthly.reset_index(), components, score, band, confidence,
                          reasons, profile, proposal)
