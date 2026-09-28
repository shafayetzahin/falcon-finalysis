"""Validate structural and accounting consistency without changing reported values."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from core.config import FIELDS


@dataclass(frozen=True)
class Issue:
    severity: str
    year: str
    message: str


def validate(frame: pd.DataFrame, tolerance: float = 0.01, absolute: float = 1.0) -> list[Issue]:
    """Return errors and warnings; tolerance is relative to the larger reconciled amount."""
    issues: list[Issue] = []
    if frame.empty or 'Year' not in frame:
        return [Issue('ERROR', '', 'Provide a nonempty table with a Year column.')]
    if not 3 <= len(frame) <= 10:
        issues.append(Issue('ERROR', '', 'Provide 3–10 full fiscal years.'))
    years = pd.to_numeric(frame['Year'], errors='coerce')
    if years.isna().any() or not np.isfinite(years).all() or ((years % 1) != 0).any():
        return issues + [Issue('ERROR', '', 'Years must be whole numbers, for example 2025.')]
    if years.duplicated().any():
        issues.append(Issue('ERROR', '', 'Duplicate fiscal years are not allowed.'))
    if (years < 1900).any() or (years > 2200).any():
        issues.append(Issue('ERROR', '', 'Years must be between 1900 and 2200.'))
    ordered = sorted(years.astype(int))
    if any(b - a != 1 for a, b in zip(ordered, ordered[1:])):
        issues.append(Issue('ERROR', '', 'Use consecutive annual periods; missing years distort averages.'))
    for col in frame.columns:
        if col == 'Year':
            continue
        values = pd.to_numeric(frame[col], errors='coerce')
        bad = frame[col].notna() & (values.isna() | ~np.isfinite(values))
        if bad.any():
            issues.append(Issue('ERROR', '', f'{col}: enter finite numbers or leave cells blank.'))
    if any(i.severity == 'ERROR' for i in issues):
        return issues
    df = frame.set_index('Year').reindex(columns=FIELDS).astype(float).sort_index()
    checks = [
        ('balance sheet', 'Total Assets', ['Total Liabilities', 'Shareholders Equity'], [1, 1]),
        ('gross profit', 'Gross Profit', ['Revenue', 'COGS'], [1, -1]),
        ('EBITDA', 'EBITDA', ['Gross Profit', 'Operating Expenses'], [1, -1]),
        ('EBIT', 'EBIT', ['EBITDA', 'Depreciation'], [1, -1]),
        ('EBT', 'EBT', ['EBIT', 'Interest Expense'], [1, -1]),
        ('net income', 'Net Income', ['EBT', 'Tax Expense'], [1, -1]),
        ('current assets', 'Total Current Assets', ['Cash', 'Accounts Receivable', 'Inventory', 'Other Current Assets'], [1]*4),
        ('total assets', 'Total Assets', ['Total Current Assets', 'Property Plant Equipment', 'Other Non-Current Assets'], [1]*3),
        ('current liabilities', 'Total Current Liabilities', ['Accounts Payable', 'Short-Term Debt', 'Other Current Liabilities'], [1]*3),
        ('total liabilities', 'Total Liabilities', ['Total Current Liabilities', 'Long-Term Debt', 'Other Non-Current Liabilities'], [1]*3),
    ]
    for year, row in df.iterrows():
        for label, target, inputs, signs in checks:
            if row[[target] + inputs].notna().all():
                expected = sum(row[k] * s for k, s in zip(inputs, signs))
                diff = row[target] - expected
                if abs(diff) > max(absolute, tolerance * max(abs(expected), abs(row[target]))):
                    issues.append(Issue('WARNING', str(int(year)), f'{label} is out of balance by {diff:,.2f}.'))
        for col in ['Revenue', 'COGS', 'Operating Expenses', 'Depreciation', 'Interest Expense',
                    'Capital Expenditure', 'Cash Dividends', 'Cash', 'Inventory', 'Accounts Receivable',
                    'Accounts Payable', 'Short-Term Debt', 'Long-Term Debt', 'Total Assets',
                    'Total Current Assets', 'Total Current Liabilities', 'Shares Outstanding',
                    'Weighted Average Shares Outstanding']:
            if row[col] < 0:
                issues.append(Issue('WARNING', str(int(year)), f'{col} is negative; review the sign convention.'))
        if row['Shareholders Equity'] <= 0:
            issues.append(Issue('WARNING', str(int(year)), 'Nonpositive equity: equity-based ratios are unavailable.'))
    for pos in range(1, len(df)):
        row, prev = df.iloc[pos], df.iloc[pos-1]
        keys = ['Cash', 'Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow']
        if row[keys].notna().all() and pd.notna(prev['Cash']):
            fx = row['FX Effect on Cash'] if pd.notna(row['FX Effect on Cash']) else 0
            expected = prev['Cash'] + row[keys[1:]].sum() + fx
            diff = row['Cash'] - expected
            if abs(diff) > max(absolute, tolerance * max(abs(expected), abs(row['Cash']))):
                issues.append(Issue('WARNING', str(int(df.index[pos])),
                                    f'Cash reconciliation differs by {diff:,.2f}; omitted FX effects assumed zero.'))
    missing = [c for c in FIELDS[:32] if df[c].isna().any()]
    if missing:
        issues.append(Issue('INFO', '', 'Incomplete inputs: ' + ', '.join(missing) + '. Related metrics may be N/A.'))
    return issues
