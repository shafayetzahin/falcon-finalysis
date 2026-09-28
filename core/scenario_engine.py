"""Explicit one-year operating scenario, frozen-capital returns and cash flow proxy."""
from dataclasses import dataclass, asdict, replace
import numpy as np
import pandas as pd

ASSUMPTIONS = (
    'One-year operating model. COGS and cash operating expenses are percentages of projected revenue; '
    'operating expenses exclude depreciation. Depreciation stays at the latest reported amount. '
    'Interest equals scenario ending debt × interest rate. Tax applies only to positive pretax profit; '
    'no tax-loss benefit is assumed. Receivable, inventory and payable days determine projected ending balances '
    'using revenue or COGS / 365. Operating working capital = receivables + inventory - payables. '
    'OCF proxy = net income + depreciation - change in operating working capital. '
    'FCF proxy = OCF proxy - capex. Other accruals, provisions, tax timing and financing cash flows are excluded. '
    'ROA and ROE use frozen latest total assets and equity; debt-to-equity uses frozen equity. '
    'These are scenario return proxies, not a balanced three-statement forecast. Base case uses zero revenue '
    'growth and latest cost ratios, debt and ending-balance days; historical average-balance days differ.'
)


@dataclass(frozen=True)
class Scenario:
    revenue_growth: float
    cogs_ratio: float
    opex_ratio: float
    interest_rate: float
    tax_rate: float
    receivable_days: float
    inventory_days: float
    payable_days: float
    capex: float
    debt: float

    def to_dict(self) -> dict:
        return asdict(self)


def baseline(row: pd.Series) -> Scenario:
    required = ['Revenue', 'COGS', 'Operating Expenses', 'Interest Expense', 'EBT', 'Tax Expense',
                'Accounts Receivable', 'Inventory', 'Accounts Payable', 'Capital Expenditure',
                'Short-Term Debt', 'Long-Term Debt', 'Depreciation', 'Total Assets', 'Shareholders Equity']
    if any(pd.isna(row.get(k)) or not np.isfinite(row.get(k)) for k in required):
        raise ValueError('Scenario Lab needs revenue, expenses, tax, working capital, debt, depreciation, assets and equity. Complete these inputs first.')
    if row['Revenue'] <= 0 or row['COGS'] <= 0:
        raise ValueError('Scenario Lab needs positive revenue and COGS for operating-day assumptions.')
    debt = row['Short-Term Debt'] + row['Long-Term Debt']
    return Scenario(0, row['COGS']/row['Revenue'], row['Operating Expenses']/row['Revenue'],
                    row['Interest Expense']/debt if debt > 0 else 0,
                    float(np.clip(row['Tax Expense']/row['EBT'], 0, 1)) if row['EBT'] > 0 else 0,
                    row['Accounts Receivable']/row['Revenue']*365, row['Inventory']/row['COGS']*365,
                    row['Accounts Payable']/row['COGS']*365, row['Capital Expenditure'], debt)


def model(row: pd.Series, case: Scenario) -> pd.Series:
    """Never mutate actual statements. Finite assumptions and positive-denominator policies apply."""
    baseline(row)  # Validate actual dependencies even for a user-supplied case.
    if any(not np.isfinite(v) for v in asdict(case).values()):
        raise ValueError('Scenario assumptions must be finite numbers.')
    if case.revenue_growth <= -1 or case.revenue_growth > 5:
        raise ValueError('Revenue growth must exceed -100% and be at most 500%.')
    if any(v < 0 for k, v in asdict(case).items() if k != 'revenue_growth'):
        raise ValueError('Scenario costs, days, rates, debt and capex cannot be negative.')
    if any(v > 1 for v in [case.tax_rate, case.interest_rate]) or case.cogs_ratio > 2 or case.opex_ratio > 2:
        raise ValueError('Tax and interest rates must be at most 100%; cost ratios at most 200%.')
    revenue = row['Revenue'] * (1 + case.revenue_growth)
    cogs, opex = revenue * case.cogs_ratio, revenue * case.opex_ratio
    gross, ebitda = revenue-cogs, revenue-cogs-opex
    ebit = ebitda-row['Depreciation']
    interest = case.debt*case.interest_rate
    tax = max(ebit-interest, 0)*case.tax_rate
    net = ebit-interest-tax
    ar, inventory, ap = revenue/365*case.receivable_days, cogs/365*case.inventory_days, cogs/365*case.payable_days
    wc = ar+inventory-ap
    previous_wc = row['Accounts Receivable']+row['Inventory']-row['Accounts Payable']
    ocf = net+row['Depreciation']-(wc-previous_wc)
    return pd.Series({'Revenue': revenue, 'Gross Profit': gross, 'EBITDA': ebitda, 'EBIT': ebit,
                      'Interest': interest, 'Tax': tax, 'Net Income': net, 'Net Margin': net/revenue,
                      'ROA': net/row['Total Assets'] if row['Total Assets'] > 0 else np.nan,
                      'ROE': net/row['Shareholders Equity'] if row['Shareholders Equity'] > 0 else np.nan,
                      'Operating Cash Flow proxy': ocf, 'Free Cash Flow': ocf-case.capex,
                      'Operating Working Capital': wc,
                      'Cash Conversion Cycle': case.inventory_days+case.receivable_days-case.payable_days,
                      'Debt-to-Equity': case.debt/row['Shareholders Equity'] if row['Shareholders Equity'] > 0 else np.nan,
                      'Interest Coverage': ebit/interest if interest > 0 else np.nan})


def sensitivity(row: pd.Series, case: Scenario, output: str) -> pd.DataFrame:
    """One-at-a-time shocks around the active case; ratios use percentage-point shocks."""
    shocks = [('Revenue growth', 'revenue_growth', .05), ('Gross margin', 'cogs_ratio', -.05),
              ('Operating expenses', 'opex_ratio', .03), ('Interest rate', 'interest_rate', .02),
              ('Receivable days', 'receivable_days', 10.), ('Inventory days', 'inventory_days', 10.)]
    center = model(row, case)[output]
    rows = []
    for name, field, step in shocks:
        base_value = getattr(case, field)
        low, high = base_value-step, base_value+step
        if field == 'revenue_growth':
            low, high = max(-.99, low), min(5., high)
        else:
            upper = 1 if field == 'interest_rate' else 2 if field in ['cogs_ratio', 'opex_ratio'] else np.inf
            low, high = min(upper, max(0, low)), min(upper, max(0, high))
        left = model(row, replace(case, **{field: low}))[output]
        right = model(row, replace(case, **{field: high}))[output]
        rows.append({'Driver': name, 'Minus-shock assumption': 1-low if name == 'Gross margin' else low,
                     'Plus-shock assumption': 1-high if name == 'Gross margin' else high,
                     'Minus shock': left, 'Base': center, 'Plus shock': right,
                     'Impact range': abs(right-left)})
    return pd.DataFrame(rows).sort_values('Impact range', ascending=False)
