"""Review-first transaction import for CredGrid AI."""
from __future__ import annotations

from io import BytesIO, StringIO
import re

import pandas as pd

from core.credit_engine import TRANSACTION_COLUMNS


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
    "Business revenue": ["sale", "payment received", "marketplace", "customer", "cash deposit"],
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
    text = series.astype("string").str.replace(",", "", regex=False).str.strip()
    negative = text.str.match(r"^\(.*\)$", na=False)
    text = text.str.replace(r"[()৳$€£]", "", regex=True)
    values = pd.to_numeric(text, errors="coerce")
    values.loc[negative] *= -1
    return values


def normalize_transactions(raw: pd.DataFrame, source: str) -> pd.DataFrame:
    if raw.empty:
        raise ValueError("The transaction file is empty.")
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
    frame["Date"] = pd.to_datetime(raw[mapped["Date"]], errors="coerce", dayfirst=True)
    frame["Description"] = (raw[mapped["Description"]].astype("string")
                            if "Description" in mapped else "")
    if "Amount" in mapped:
        frame["Amount"] = _number(raw[mapped["Amount"]])
    else:
        credit = _number(raw[mapped["Credit"]]) if "Credit" in mapped else 0.0
        debit = _number(raw[mapped["Debit"]]) if "Debit" in mapped else 0.0
        frame["Amount"] = pd.Series(credit, index=raw.index).fillna(0) - pd.Series(
            debit, index=raw.index).fillna(0)
    frame["Balance"] = _number(raw[mapped["Balance"]]) if "Balance" in mapped else pd.NA
    frame["Category"] = raw[mapped["Category"]].astype("string") if "Category" in mapped else "Unreviewed"
    frame["Source"] = source
    frame = frame.dropna(subset=["Date", "Amount"])
    frame = frame[frame["Amount"] != 0].sort_values("Date").reset_index(drop=True)
    if frame.empty:
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
    ])


def read_transaction_file(content: bytes, name: str, sheet: str | None = None) -> pd.DataFrame:
    lower = name.lower()
    if lower.endswith(".csv"):
        raw = pd.read_csv(StringIO(content.decode("utf-8-sig")))
        return normalize_transactions(raw, name)
    if lower.endswith(".xlsx"):
        raw = pd.read_excel(BytesIO(content), sheet_name=sheet or 0, engine="openpyxl")
        return normalize_transactions(raw, name + (f" · sheet {sheet}" if sheet else ""))
    if lower.endswith(".pdf"):
        import pdfplumber
        frames = []
        with pdfplumber.open(BytesIO(content)) as document:
            for page_number, page in enumerate(document.pages, 1):
                for table in page.extract_tables() or []:
                    if len(table) >= 2:
                        header = [str(cell or "").strip() for cell in table[0]]
                        candidate = pd.DataFrame(table[1:], columns=header)
                        try:
                            frames.append(normalize_transactions(candidate,
                                                                 f"{name} · page {page_number}"))
                        except ValueError:
                            continue
        if not frames:
            raise ValueError("No transaction table could be read from this PDF. Use a text-based statement or export CSV/XLSX from the provider.")
        return pd.concat(frames, ignore_index=True).drop_duplicates().sort_values("Date")
    raise ValueError("Upload a CSV, XLSX or text-based PDF statement.")
