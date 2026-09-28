"""Explain which analyses the current financial dataset can support."""
from __future__ import annotations

import pandas as pd


ANALYSIS_REQUIREMENTS = {
    "Performance overview": ["Revenue", "Net Income", "Operating Cash Flow"],
    "Profitability": ["Revenue", "Gross Profit", "Operating Profit", "Net Income"],
    "Liquidity": ["Current Assets", "Current Liabilities", "Inventory"],
    "Leverage & coverage": ["Total Liabilities", "Shareholders Equity", "EBIT", "Interest Expense"],
    "Operating efficiency": ["Revenue", "COGS", "Inventory", "Accounts Receivable", "Accounts Payable"],
    "Cash generation": ["Operating Cash Flow", "Capital Expenditure"],
    "DuPont": ["Revenue", "Net Income", "Total Assets", "Shareholders Equity"],
    "Per-share & market": ["Net Income", "Weighted Average Shares Outstanding",
                           "Shares Outstanding", "Market Price per Share"],
}


def readiness(frame: pd.DataFrame) -> pd.DataFrame:
    """Return transparent coverage and missing-field reasons by analysis area."""
    rows = []
    periods = max(len(frame), 1)
    for area, fields in ANALYSIS_REQUIREMENTS.items():
        available = {field: int(frame[field].notna().sum()) if field in frame else 0 for field in fields}
        missing_latest = [field for field in fields
                          if field not in frame or frame.empty or pd.isna(frame.iloc[-1].get(field))]
        coverage = sum(available.values()) / (len(fields) * periods)
        rows.append({
            "Analysis area": area,
            "Status": "Ready" if not missing_latest else "Needs data",
            "Coverage": coverage,
            "Missing latest-year fields": ", ".join(missing_latest) if missing_latest else "None",
            "Available observations": sum(available.values()),
            "Required observations": len(fields) * periods,
        })
    return pd.DataFrame(rows)


def field_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize completion for every financial field that exists in the frame."""
    rows = []
    periods = max(len(frame), 1)
    for field in [column for column in frame.columns if column != "Year"]:
        count = int(frame[field].notna().sum())
        rows.append({"Field": field, "Available years": count, "Total years": periods,
                     "Coverage": count / periods, "Missing years": periods - count})
    return pd.DataFrame(rows).sort_values(["Coverage", "Field"]).reset_index(drop=True)
