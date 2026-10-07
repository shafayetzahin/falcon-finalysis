"""Aligned public-company comparison tables with explicit period handling."""
from __future__ import annotations

import numpy as np
import pandas as pd


EXCHANGE_METRICS = ["Net Income", "Basic EPS", "NAV per Share", "Cash Dividend", "Stock Dividend", "Dividend", "Dividend Yield"]


def exchange_metric_comparison(details: dict[str, pd.DataFrame], year: int | None = None) -> pd.DataFrame:
    """Combine exchange-provided annual observations for one reviewed fiscal year."""
    if not details:
        raise ValueError("Load exchange details for at least one company.")
    years_by_company, cleaned = {}, {}
    for ticker, frame in details.items():
        if frame.empty:
            continue
        if not {"Year", "Exchange metric", "Value"}.issubset(frame):
            raise ValueError(f"{ticker}: exchange metrics need Year, Exchange metric and Value columns.")
        normalized = frame.copy()
        years = pd.to_numeric(normalized["Year"], errors="coerce")
        if years.isna().any() or not np.isfinite(years).all() or (years % 1 != 0).any():
            raise ValueError(f"{ticker}: fiscal years must be finite whole numbers.")
        normalized["Year"] = years.astype(int)
        normalized["Value"] = pd.to_numeric(normalized["Value"], errors="coerce").replace(
            [np.inf, -np.inf], np.nan)
        if normalized.duplicated(["Year", "Exchange metric"]).any():
            raise ValueError(f"{ticker}: duplicate metrics for the same fiscal year must be reviewed.")
        cleaned[ticker] = normalized
        years_by_company[ticker] = set(normalized["Year"])
    if not years_by_company:
        raise ValueError("No dated exchange metrics are available.")
    if year is not None and (not np.isfinite(year) or year != int(year)):
        raise ValueError("Comparison fiscal year must be a finite whole number.")
    common = set.intersection(*years_by_company.values()) if years_by_company else set()
    chosen_year = int(year) if year is not None else (max(common) if common else max(
        year_value for values in years_by_company.values() for year_value in values))
    rows = []
    for ticker, frame in details.items():
        row = {"Ticker": ticker, "Year": chosen_year}
        normalized = cleaned.get(ticker)
        selected = (normalized[normalized["Year"].eq(chosen_year)] if normalized is not None
                    else pd.DataFrame(columns=["Exchange metric", "Value"]))
        for metric in EXCHANGE_METRICS:
            values = selected[selected["Exchange metric"].eq(metric)]["Value"]
            row[metric] = float(values.iloc[-1]) if not values.empty else pd.NA
        rows.append(row)
    return pd.DataFrame(rows).set_index("Ticker")


def comparison_strengths(frame: pd.DataFrame, higher_is_better: list[str]) -> pd.DataFrame:
    """Show each company's position without producing a composite ranking."""
    rows = []
    for metric in frame.columns:
        values = pd.to_numeric(frame[metric], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if values.empty:
            continue
        preferred = values.idxmax() if metric in higher_is_better else values.idxmin()
        rows.append({"Metric": metric, "Reference leader": preferred,
                     "Reference value": float(values.loc[preferred]),
                     "Direction": "Higher" if metric in higher_is_better else "Lower"})
    return pd.DataFrame(rows)
