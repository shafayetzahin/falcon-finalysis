"""Review-first transaction import for CredGrid AI."""
from __future__ import annotations

from io import BytesIO
import re

import numpy as np
import pandas as pd

from core.credit_engine import TRANSACTION_COLUMNS
from data.parsers import numeric_values, parse_date, read_tabular


ALIASES = {
    "Date": ["date", "transaction date", "txn date", "posting date", "value date"],
    "Description": ["description", "details", "narration", "particulars", "remarks", "memo"],
    "Amount": ["amount", "transaction amount", "signed amount"],
    "Credit": ["credit", "deposit", "money in", "inflow", "cr"],
    "Debit": ["debit", "withdrawal", "money out", "outflow", "dr"],
    "Balance": ["balance", "running balance", "closing balance"],
    "Category": ["category", "transaction category"],
}

CATEGORY_RULES = {
    "Business revenue": ["sale", "payment received", "marketplace", "customer"],
    "Inventory": ["inventory", "supplier", "stock purchase", "wholesale"],
    "Rent": ["rent", "lease"],
    "Utilities": ["utility", "electric", "internet", "mobile", "gas", "water"],
    "Delivery": ["delivery", "courier", "shipping", "transport"],
    "Debt service": ["loan", "emi", "installment", "finance payment"],
    "Returned payment": ["return", "reversal", "bounce", "dishonour", "failed"],
}


def _label(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _number(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.replace(r"[৳$€£]", "", regex=True)
    return numeric_values(text)


def normalize_transactions(raw: pd.DataFrame, source: str) -> pd.DataFrame:
    raw = raw.dropna(how="all")
    if raw.empty:
        raise ValueError("The transaction file is empty.")
    labels = [_label(column) for column in raw.columns]
    if len(labels) != len(set(labels)):
        raise ValueError("Use unique transaction column headers.")
    if len(raw) > 5000 or len(raw.columns) > 100:
        raise ValueError("Use at most 5,000 transaction rows and 100 columns.")
    lookup = {_label(column): column for column in raw.columns}
    mapped = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if alias in lookup:
                mapped[target] = lookup[alias]
                break
    if "Date" not in mapped:
        raise ValueError("Could not find a transaction date column.")
    if "Amount" not in mapped and not ({"Credit", "Debit"} & set(mapped)):
        raise ValueError("Provide Amount, or Credit and Debit columns.")
    frame = pd.DataFrame()
    frame["Date"] = raw[mapped["Date"]].map(parse_date)
    frame["Description"] = (raw[mapped["Description"]].astype("string")
                            if "Description" in mapped else "")
    numeric = {}
    for target in ["Amount", "Credit", "Debit", "Balance"]:
        if target not in mapped:
            continue
        source_values = raw[mapped[target]]
        values = _number(source_values)
        present = source_values.notna() & source_values.astype("string").str.strip().ne("")
        if (present & (values.isna() | ~np.isfinite(values))).any():
            raise ValueError(f"{target} contains invalid values. Use finite numbers, or blank for unavailable values.")
        numeric[target] = values
    if "Amount" in mapped:
        frame["Amount"] = numeric["Amount"]
    else:
        credit = numeric["Credit"] if "Credit" in mapped else 0.0
        debit = numeric["Debit"] if "Debit" in mapped else 0.0
        for target in ["Credit", "Debit"]:
            if target in numeric and (numeric[target] < 0).any():
                raise ValueError("Credit and Debit must be non-negative. Use a signed Amount column for negative amounts.")
        supplied = pd.concat([value.notna() for key, value in numeric.items()
                              if key in {"Credit", "Debit"}], axis=1).any(axis=1)
        if not supplied.all():
            raise ValueError("Every transaction row needs Amount, Credit or Debit. Correct the missing values.")
        frame["Amount"] = pd.Series(credit, index=raw.index).fillna(0) - pd.Series(
            debit, index=raw.index).fillna(0)
    frame["Balance"] = numeric["Balance"] if "Balance" in mapped else pd.NA
    frame["Category"] = raw[mapped["Category"]].astype("string") if "Category" in mapped else "Unreviewed"
    frame["Source"] = source
    if frame[["Date", "Amount"]].isna().any().any():
        raise ValueError("Every transaction row needs a valid Date and Amount. Correct the missing or invalid values.")
    frame = frame.sort_values("Date", kind="stable").reset_index(drop=True)
    if not (frame["Amount"] != 0).any():
        raise ValueError("No valid dated nonzero transactions were found.")
    return frame.reindex(columns=TRANSACTION_COLUMNS)


def suggest_transaction_categories(frame: pd.DataFrame) -> pd.DataFrame:
    """Suggest categories from disclosed keywords without replacing reviewed categories."""
    out = frame.copy().reindex(columns=TRANSACTION_COLUMNS)
    descriptions = out["Description"].fillna("").astype(str).str.lower()
    current = out["Category"].fillna("").astype(str).str.strip()
    suggestions = []
    for description, amount, category in zip(descriptions, out["Amount"], current):
        if category and category.lower() not in {"unreviewed", "uncategorized"}:
            suggestions.append(category)
            continue
        positive = pd.to_numeric(amount, errors='coerce') > 0
        if re.search(r'return|reversal|bounce|dishonou?r|failed', description):
            matched = 'Returned payment'
        elif re.search(r'loan|emi|installment|instalment|finance payment|debt repayment', description):
            matched = 'Loan proceeds' if positive else 'Debt service'
        elif re.search(r'owner|capital contribution|personal|gift|salary|transfer', description):
            matched = 'Owner / personal transfer' if positive else 'Other outflow'
        else:
            matched = next((name for name, terms in CATEGORY_RULES.items()
                            if any(term in description for term in terms)), None)
        if matched is None:
            matched = "Other inflow" if pd.to_numeric(amount, errors="coerce") > 0 else "Other outflow"
        suggestions.append(matched)
    out["Category"] = suggestions
    return out


def evidence_checks(frame: pd.DataFrame) -> pd.DataFrame:
    """Return deterministic transaction-review indicators for a human reviewer."""
    clean = frame.copy().reindex(columns=TRANSACTION_COLUMNS)
    clean["Amount"] = pd.to_numeric(clean["Amount"], errors="coerce")
    clean["Description"] = clean["Description"].fillna("").astype(str)
    clean["Category"] = clean["Category"].fillna("").astype(str)
    inflows = clean[clean["Amount"] > 0]
    total_inflows = float(inflows["Amount"].sum())
    grouped = inflows.groupby(inflows["Description"].str.lower().str.strip())["Amount"].sum()
    concentration = float(grouped.max() / total_inflows) if total_inflows and not grouped.empty else 0.0
    returned = clean[clean["Description"].str.contains(
        r"return|reversal|bounce|dishonou?r|failed", case=False, regex=True)]
    debt = clean[(clean["Amount"] < 0) & clean["Category"].str.contains(
        r"debt|loan|emi|installment", case=False, regex=True)]
    uncategorized = clean["Category"].str.lower().isin(["", "unreviewed", "uncategorized"])
    duplicates = clean.duplicated(["Date", "Description", "Amount", "Balance"], keep=False)
    return pd.DataFrame([
        {"Indicator": "Largest described inflow concentration", "Value": f"{concentration:.0%}",
         "Status": "REVIEW" if concentration > .50 else "OK",
         "Reviewer note": "Confirm whether repeated descriptions represent one customer or an aggregated sales channel."},
        {"Indicator": "Returned/failed-payment references", "Value": str(len(returned)),
         "Status": "REVIEW" if len(returned) else "OK",
         "Reviewer note": "Verify reversals and whether they indicate repayment or collection stress."},
        {"Indicator": "Categorized debt-service transactions", "Value": str(len(debt)),
         "Status": "REVIEW" if len(debt) else "INFO",
         "Reviewer note": "Reconcile observed payments with declared existing obligations."},
        {"Indicator": "Unreviewed transaction categories", "Value": str(int(uncategorized.sum())),
         "Status": "REVIEW" if uncategorized.any() else "OK",
         "Reviewer note": "Review material categories before relying on expense and obligation totals."},
        {"Indicator": "Potential duplicate transactions", "Value": str(int(duplicates.sum())),
         "Status": "REVIEW" if duplicates.any() else "OK",
         "Reviewer note": "Confirm repeated rows against statement references; identical legitimate transactions are retained."},
    ])


def read_transaction_file(content: bytes, name: str, sheet: str | None = None) -> pd.DataFrame:
    if not content or len(content) > 10 * 1024 * 1024:
        raise ValueError("Use a non-empty statement smaller than 10 MB.")
    lower = name.lower()
    if lower.endswith((".csv", ".xlsx")):
        raw = read_tabular(content, name, sheet, max_rows=5000)
        return normalize_transactions(raw, name + (f" · sheet {sheet}" if sheet else ""))
    if lower.endswith(".pdf"):
        import pdfplumber
        frames = []
        try:
            with pdfplumber.open(BytesIO(content)) as document:
                if len(document.pages) > 100:
                    raise ValueError("Use a statement with at most 100 pages.")
                for page_number, page in enumerate(document.pages, 1):
                    for table in page.extract_tables() or []:
                        if len(table) < 2:
                            continue
                        header = [str(cell or "").strip() for cell in table[0]]
                        labels = {_label(cell) for cell in header}
                        if not (labels.intersection(ALIASES["Date"])
                                and labels.intersection(ALIASES["Amount"] + ALIASES["Credit"] + ALIASES["Debit"])):
                            continue
                        candidate = pd.DataFrame(table[1:], columns=header)
                        frames.append(normalize_transactions(candidate, f"{name} · page {page_number}"))
                        if sum(len(frame) for frame in frames) > 5000:
                            raise ValueError("Use at most 5,000 transaction rows per upload.")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Unable to read this PDF statement. Use a text-based PDF or export CSV/XLSX.") from exc
        if not frames:
            raise ValueError("No transaction table could be read from this PDF. Use a text-based statement or export CSV/XLSX from the provider.")
        return pd.concat(frames, ignore_index=True).sort_values("Date", kind="stable").reset_index(drop=True)
    raise ValueError("Upload a CSV, XLSX or text-based PDF statement.")
