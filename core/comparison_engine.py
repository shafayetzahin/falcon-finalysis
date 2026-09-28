"""Aligned public-company comparison tables with explicit period handling."""
from __future__ import annotations

import pandas as pd


EXCHANGE_METRICS = ["Net Income", "Basic EPS", "NAV per Share", "Dividend", "Dividend Yield"]


def exchange_metric_comparison(details: dict[str, pd.DataFrame], year: int | None = None) -> pd.DataFrame:
    """Combine exchange-provided annual observations for one reviewed fiscal year."""
    if not details:
        raise ValueError("Load exchange details for at least one company.")
    years_by_company = {
        ticker: set(pd.to_numeric(frame.get("Year"), errors="coerce").dropna().astype(int))
        for ticker, frame in details.items() if not frame.empty
    }
    if not years_by_company:
        raise ValueError("No dated exchange metrics are available.")
    common = set.intersection(*years_by_company.values()) if years_by_company else set()
    chosen_year = int(year) if year is not None else (max(common) if common else max(
        year_value for values in years_by_company.values() for year_value in values))
    rows = []
    for ticker, frame in details.items():
        selected = frame[pd.to_numeric(frame["Year"], errors="coerce").eq(chosen_year)]
        row = {"Ticker": ticker, "Year": chosen_year}
        for metric in EXCHANGE_METRICS:
            values = selected[selected["Exchange metric"].eq(metric)]["Value"]
            row[metric] = float(values.iloc[-1]) if not values.empty else pd.NA
        rows.append(row)
    return pd.DataFrame(rows).set_index("Ticker")


def comparison_strengths(frame: pd.DataFrame, higher_is_better: list[str]) -> pd.DataFrame:
    """Show each company's position without producing a composite ranking."""
    rows = []
    for metric in frame.columns:
        values = pd.to_numeric(frame[metric], errors="coerce").dropna()
        if values.empty:
            continue
        preferred = values.idxmax() if metric in higher_is_better else values.idxmin()
        rows.append({"Metric": metric, "Reference leader": preferred,
                     "Reference value": float(values.loc[preferred]),
                     "Direction": "Higher" if metric in higher_is_better else "Lower"})
    return pd.DataFrame(rows)
