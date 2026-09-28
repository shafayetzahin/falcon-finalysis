"""Cell-level source records for imported and manually entered financial values."""
from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd

PROVENANCE_COLUMNS = ["Year", "Field", "Source Type", "Source Reference", "Recorded At"]


def provenance_for_frame(frame: pd.DataFrame, source_type: str, reference: str) -> pd.DataFrame:
    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for _, row in frame.iterrows():
        year = int(row["Year"])
        for field, value in row.items():
            if field != "Year" and pd.notna(value):
                rows.append([year, field, source_type, reference, recorded_at])
    return pd.DataFrame(rows, columns=PROVENANCE_COLUMNS)


def provenance_from_evidence(evidence: pd.DataFrame, source_type: str = "Annual report extraction",
                             accepted_frame: pd.DataFrame | None = None) -> pd.DataFrame:
    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for _, row in evidence.iterrows():
        rows.append([int(row["Year"]), str(row["Falcon Finalysis field"]), source_type,
                     str(row.get("Source", "")), recorded_at])
    result = pd.DataFrame(rows, columns=PROVENANCE_COLUMNS).drop_duplicates(["Year", "Field"], keep="first")
    if accepted_frame is not None:
        accepted = {(int(row['Year']), field) for _, row in accepted_frame.iterrows()
                    for field, value in row.items() if field != 'Year' and pd.notna(value)}
        result = result[result.apply(lambda row: (int(row['Year']), row['Field']) in accepted, axis=1)]
    return result.reset_index(drop=True)


def merge_provenance(current: pd.DataFrame | None, incoming: pd.DataFrame) -> pd.DataFrame:
    base = current if isinstance(current, pd.DataFrame) else pd.DataFrame(columns=PROVENANCE_COLUMNS)
    combined = pd.concat([base, incoming], ignore_index=True).drop_duplicates(["Year", "Field"], keep="last")
    return combined.reindex(columns=PROVENANCE_COLUMNS).sort_values(["Year", "Field"]).reset_index(drop=True)


def changed_provenance(before: pd.DataFrame, after: pd.DataFrame, reference: str = "Manual editor") -> pd.DataFrame:
    old = before.set_index("Year") if not before.empty else pd.DataFrame()
    changed = []
    for _, row in after.iterrows():
        year = int(row["Year"])
        for field, value in row.items():
            if field == "Year" or pd.isna(value):
                continue
            previous = old.at[year, field] if year in old.index and field in old.columns else pd.NA
            if pd.isna(previous) or float(previous) != float(value):
                changed.append({"Year": year, field: value})
    if not changed:
        return pd.DataFrame(columns=PROVENANCE_COLUMNS)
    records = []
    for item in changed:
        year = item.pop("Year")
        for field in item:
            records.append({"Year": year, field: item[field]})
    return provenance_for_frame(pd.DataFrame(records).fillna(pd.NA), "Manual entry", reference)
