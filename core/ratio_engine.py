"""Metric registry with explicit dependencies, formulas and unavailable reasons."""
from dataclasses import dataclass
from typing import Callable
import numpy as np
import pandas as pd
from core.config import FIELDS


@dataclass(frozen=True)
class Metric:
    name: str
    category: str
    unit: str
    formula: str
    numerator: Callable
    denominator: Callable | None = None
    inputs: tuple[str, ...] = ()


def v(key: str) -> Callable:
    return lambda r: r[key]


def sub(a: str, b: str) -> Callable:
    return lambda r: r[a] - r[b]


def add(a: str, b: str) -> Callable:
    return lambda r: r[a] + r[b]


METRICS: list[Metric] = []


def register(name: str, category: str, unit: str, formula: str, n: Callable,
             d: Callable | None = None, inputs: tuple = ()) -> None:
    class Probe(dict):
        def __getitem__(self, key):
            self[key] = 1.0
            return 1.0
    probe = Probe()
    n(probe)
    if d:
        d(probe)
    METRICS.append(Metric(name, category, unit, formula, n, d, inputs or tuple(probe)))


for name, numerator in [('Current Ratio', v('Total Current Assets')),
                         ('Quick Ratio', sub('Total Current Assets', 'Inventory')),
                         ('Cash Ratio', v('Cash')), ('Operating Cash Flow Ratio', v('Operating Cash Flow'))]:
    label = {'Current Ratio': 'Current assets', 'Quick Ratio': '(Current assets - inventory)',
             'Cash Ratio': 'Cash', 'Operating Cash Flow Ratio': 'Operating cash flow'}[name]
    register(name, 'Liquidity', 'x', label + ' / current liabilities', numerator, v('Total Current Liabilities'))
for name, source in [('Gross Profit Margin', 'Gross Profit'), ('Operating Margin', 'EBIT'),
                     ('EBITDA Margin', 'EBITDA'), ('Net Profit Margin', 'Net Income')]:
    register(name, 'Profitability', '%', source + ' / revenue', v(source), v('Revenue'))
register('ROA', 'Profitability', '%', 'Net income / average total assets', v('Net Income'), v('Average Total Assets'))
register('ROE', 'Profitability', '%', 'Net income / average equity', v('Net Income'), v('Average Shareholders Equity'))
register('ROCE', 'Profitability', '%', 'EBIT / (total assets - current liabilities)', v('EBIT'), sub('Total Assets', 'Total Current Liabilities'))
for name, numerator, balance in [('Asset Turnover', 'Revenue', 'Total Assets'),
                                 ('Inventory Turnover', 'COGS', 'Inventory'),
                                 ('Receivables Turnover', 'Revenue', 'Accounts Receivable'),
                                 ('Payables Turnover', 'COGS', 'Accounts Payable')]:
    register(name, 'Efficiency', 'x', f'{numerator} / average {balance.lower()}', v(numerator), v('Average ' + balance))
for name, balance, flow in [('Inventory Days', 'Inventory', 'COGS'),
                           ('Receivable Days', 'Accounts Receivable', 'Revenue'),
                           ('Payable Days', 'Accounts Payable', 'COGS')]:
    register(name, 'Efficiency', 'days', f'365 × average {balance.lower()} / {flow}',
             lambda r, b=balance: 365 * r['Average ' + b], v(flow))
register('Cash Conversion Cycle', 'Efficiency', 'days', 'Inventory days + receivable days - payable days',
         lambda r: r['Inventory Days'] + r['Receivable Days'] - r['Payable Days'])
register('Net Working Capital', 'Liquidity', 'money', 'Current assets - current liabilities', sub('Total Current Assets', 'Total Current Liabilities'))
register('Total Debt', 'Solvency', 'money', 'Short-term debt + long-term debt', add('Short-Term Debt', 'Long-Term Debt'))
register('Debt-to-Equity', 'Solvency', 'x', 'Interest-bearing debt / ending equity', v('Total Debt'), v('Shareholders Equity'))
register('Liabilities-to-Equity', 'Solvency', 'x', 'Total liabilities / ending equity', v('Total Liabilities'), v('Shareholders Equity'))
register('Debt Ratio', 'Solvency', '%', 'Total liabilities / total assets', v('Total Liabilities'), v('Total Assets'))
register('Long-Term Debt to Capital', 'Solvency', '%', 'Long-term debt / (long-term debt + equity)', v('Long-Term Debt'), add('Long-Term Debt', 'Shareholders Equity'))
register('Interest Coverage', 'Solvency', 'x', 'EBIT / interest expense', v('EBIT'), v('Interest Expense'))
register('Cash Interest Coverage', 'Solvency', 'x', '(OCF + cash interest + cash taxes) / cash interest; assumes OCF includes these payments',
         lambda r: r['Operating Cash Flow'] + r['Cash Interest Paid'] + r['Cash Taxes Paid'], v('Cash Interest Paid'))
register('Free Cash Flow', 'Cash Flow', 'money', 'Operating cash flow - positive capital expenditure', sub('Operating Cash Flow', 'Capital Expenditure'))
register('Operating Cash Flow Margin', 'Cash Flow', '%', 'Operating cash flow / revenue', v('Operating Cash Flow'), v('Revenue'))
register('Cash Flow to Net Income', 'Cash Flow', 'x', 'Operating cash flow / positive net income', v('Operating Cash Flow'), v('Net Income'))
register('Capex Intensity', 'Cash Flow', '%', 'Positive capital expenditure / revenue', v('Capital Expenditure'), v('Revenue'))
register('EPS', 'Market', 'money', '(Net income - preferred dividends) / weighted average shares', sub('Net Income', 'Preferred Dividends'), v('Weighted Average Shares Outstanding'))
register('P/E Ratio', 'Market', 'x', 'Market price / positive EPS', v('Market Price Per Share'), v('EPS'))
register('Book Value Per Share', 'Market', 'money', 'Positive equity / ending shares', v('Shareholders Equity'), v('Shares Outstanding'))
register('Price-to-Book', 'Market', 'x', 'Market price / positive book value per share', v('Market Price Per Share'), v('Book Value Per Share'))
register('Dividend Payout Ratio', 'Market', '%', 'Cash dividends / positive net income', v('Cash Dividends'), v('Net Income'))
register('Dividend Yield', 'Market', '%', '(Cash dividends / ending shares) / market price',
         lambda r: r['Cash Dividends'] / r['Shares Outstanding'] if r['Shares Outstanding'] > 0 else np.nan, v('Market Price Per Share'))
BY_NAME = {m.name: m for m in METRICS}


def calculate(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return numeric results and parallel reasons. Source data is never mutated."""
    if 'Year' not in frame:
        raise ValueError('Ratio analysis needs a Year column.')
    if frame['Year'].duplicated().any():
        raise ValueError('Duplicate fiscal years must be resolved before ratio analysis.')
    if frame.empty:
        empty = pd.DataFrame(columns=[metric.name for metric in METRICS], index=pd.Index([], name='Year'))
        return empty.copy(), empty.copy()
    df = frame.set_index('Year').reindex(columns=FIELDS).astype(float).sort_index()
    for key in ['Total Assets', 'Shareholders Equity', 'Inventory', 'Accounts Receivable', 'Accounts Payable']:
        avg = (df[key] + df[key].shift()) / 2
        avg.iloc[0] = df[key].iloc[0]
        if key == 'Shareholders Equity':
            avg = avg.where((df[key] > 0) & ((df[key].shift() > 0) | (df.index == df.index[0])))
        df['Average ' + key] = avg
    results, reasons = [], []
    for _, row in df.iterrows():
        context = row.to_dict()
        values, why = {}, {}
        for metric in METRICS:
            n = metric.numerator(context)
            d = metric.denominator(context) if metric.denominator else 1.0
            reason = ''
            if not np.isfinite(n) or not np.isfinite(d):
                missing = [key for key in metric.inputs if not np.isfinite(context[key])]
                reason = 'Required input or valid balance is unavailable: ' + ', '.join(missing or metric.inputs) + '.'
            elif d <= 0:
                reason = 'Denominator must be positive for a meaningful conventional ratio.'
            elif metric.name in ['Book Value Per Share', 'Long-Term Debt to Capital'] and context['Shareholders Equity'] <= 0:
                reason = 'Equity must be positive.'
            elif metric.name == 'P/E Ratio' and context['Market Price Per Share'] <= 0:
                reason = 'Market price must be positive.'
            value = np.nan if reason else n / d
            if not np.isfinite(value) and not reason:
                reason = 'Result exceeds the supported numeric range.'
                value = np.nan
            values[metric.name], why[metric.name] = value, reason
            context[metric.name] = value
        results.append(values)
        reasons.append(why)
    return pd.DataFrame(results, index=df.index), pd.DataFrame(reasons, index=df.index)
