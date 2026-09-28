"""Cross-workflow data-quality checks with plain-language remediation."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.config import FIELDS
from core.validation import validate


@dataclass(frozen=True)
class DataQualityReport:
    score: float
    coverage: float
    provenance_coverage: float
    issues: pd.DataFrame
    field_coverage: pd.DataFrame
    next_steps: list[str]


def assess_financial_data(frame: pd.DataFrame, provenance: pd.DataFrame | None = None,
                          tolerance: float = .01) -> DataQualityReport:
    """Assess completeness, structure, consistency and source traceability."""
    if frame is None or frame.empty or "Year" not in frame:
        raise ValueError("Load financial data before running a quality review.")
    data = frame.copy()
    years = pd.to_numeric(data["Year"], errors="coerce")
    rows: list[dict] = []

    def add(severity: str, check: str, detail: str, action: str) -> None:
        rows.append({"Severity": severity, "Check": check, "Finding": detail,
                     "Recommended action": action})

    invalid_years = int(years.isna().sum())
    if invalid_years:
        add("ERROR", "Fiscal years", f"{invalid_years} row(s) have an invalid year.",
            "Enter a four-digit fiscal year for every row.")
    duplicate_years = sorted(years[years.duplicated(keep=False)].dropna().astype(int).unique())
    if duplicate_years:
        add("ERROR", "Duplicate periods", f"Repeated year(s): {', '.join(map(str, duplicate_years))}.",
            "Keep one reviewed row for each fiscal year.")
    valid_years = sorted(years.dropna().astype(int).unique())
    if len(valid_years) >= 2:
        missing_years = sorted(set(range(valid_years[0], valid_years[-1] + 1)) - set(valid_years))
        if missing_years:
            add("WARNING", "Period continuity", f"Missing year(s): {', '.join(map(str, missing_years))}.",
                "Add the missing periods or document why they are unavailable.")

    available_fields = [column for column in FIELDS if column in data]
    numeric = data.reindex(columns=available_fields).apply(pd.to_numeric, errors="coerce")
    total_cells = max(len(data) * len(FIELDS), 1)
    coverage = float(numeric.notna().sum().sum() / total_cells)
    latest_missing = [field for field in available_fields if pd.isna(numeric.iloc[-1][field])]
    if latest_missing:
        add("WARNING", "Latest-period coverage", f"{len(latest_missing)} field(s) are blank in the latest period.",
            "Complete material latest-year fields before relying on current ratios.")

    field_rows = []
    for field in FIELDS:
        series = numeric[field] if field in numeric else pd.Series(dtype=float)
        field_rows.append({"Field": field, "Available periods": int(series.notna().sum()),
                           "Coverage": float(series.notna().mean()) if len(data) else 0.0})
        values = series.dropna().astype(float)
        if len(values) >= 5:
            median = float(values.median())
            deviations = (values - median).abs()
            mad = float(deviations.median())
            if mad > 0:
                outliers = values[deviations / mad > 8]
                for index, value in outliers.items():
                    add("REVIEW", "Unusual movement",
                        f"{field} in {int(years.iloc[index])} is far from its multi-year pattern ({value:,.2f}).",
                        "Confirm the source, unit and sign; legitimate one-off events may remain.")

    reconciliation = validate(data, tolerance)
    for issue in reconciliation:
        add(issue.severity, "Accounting consistency", f"{issue.year}: {issue.message}",
            "Check the source statement, mapping, sign and reporting unit.")

    recorded = 0
    populated = int(numeric.notna().sum().sum())
    if isinstance(provenance, pd.DataFrame) and not provenance.empty:
        recorded = len(provenance.drop_duplicates(["Year", "Field"]))
    provenance_coverage = float(min(recorded / populated, 1.0)) if populated else 0.0
    if provenance_coverage < .8:
        add("REVIEW", "Source traceability", f"{provenance_coverage:.0%} of populated values have a recorded source.",
            "Attach the file, page, worksheet or manual-entry reference for material values.")

    penalty = sum({"ERROR": 15, "WARNING": 7, "REVIEW": 3}.get(row["Severity"], 0) for row in rows)
    score = float(np.clip(100 * (.65 * coverage + .35 * provenance_coverage) - penalty, 0, 100))
    next_steps = [row["Recommended action"] for row in rows[:5]]
    if not next_steps:
        next_steps = ["Continue to analysis and retain the reviewed source documents."]
    return DataQualityReport(score, coverage, provenance_coverage, pd.DataFrame(rows),
                             pd.DataFrame(field_rows), next_steps)
