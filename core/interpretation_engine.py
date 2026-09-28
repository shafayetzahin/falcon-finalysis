"""Deterministic, data-grounded prose. Replaceable without changing calculations."""
from dataclasses import dataclass
import pandas as pd
from core.trend_engine import describe, LOWER_BETTER
from core.ratio_engine import BY_NAME


def display(value: float, unit: str = '') -> str:
    if value is None or pd.isna(value):
        return 'N/A'
    if unit == '%':
        return f'{value:.1%}'
    return f'{value:,.2f}' + ('x' if unit == 'x' else ' days' if unit == 'days' else '')


@dataclass
class MetricResult:
    metric_name: str
    current_value: float
    previous_value: float
    change: float
    change_pct: float
    trend: str
    status: str
    severity: str
    interpretation: str


def interpret(metric: str, data: pd.DataFrame, reason: str = '') -> MetricResult:
    series = data[metric]
    state = describe(series, metric in LOWER_BETTER)
    current, previous = state['Current'], state['Previous']
    unit = BY_NAME[metric].unit if metric in BY_NAME else ''
    status, severity = 'Review in context', 'INFO'
    if pd.isna(current):
        prose = 'N/A. ' + (reason or 'Required inputs are unavailable.')
        status = 'Unavailable'
    else:
        prose = f'{metric} is {display(current, unit)}.'
        if pd.notna(previous):
            delta = current - previous
            movement = f'{delta*100:+.1f} percentage points' if unit == '%' else f'{delta:+,.2f}'
            prose += f' Previous: {display(previous, unit)}; change: {movement}.'
        if metric == 'Current Ratio':
            status, severity = ('Weak liquidity', 'WARNING') if current < 1 else ('Current asset coverage', 'INFO')
            prose += f' Current assets provide {current:.2f} for each 1.00 of current liabilities.'
            if current < 1:
                prose += ' Short-term liquidity appears constrained.'
            if data.iloc[-1]['Operating Cash Flow'] > 0:
                prose += ' Positive operating cash flow provides additional context but does not guarantee timely payments.'
        elif metric == 'Interest Coverage':
            status, severity = ('Limited coverage', 'WARNING') if current < 2 else ('Earnings cover interest', 'INFO')
            prose += ' This measures earnings protection for interest payments, not cash available for principal repayments.'
        elif metric in ['Net Profit Margin', 'Operating Margin', 'Gross Profit Margin']:
            status, severity = ('Negative margin', 'WARNING') if current < 0 else ('Positive margin', 'INFO')
            prose += ' Changes may reflect pricing, product mix or cost pressure; the data alone does not identify the cause.'
        elif metric == 'Debt-to-Equity':
            prose += ' Uses interest-bearing short- and long-term debt, excluding other liabilities.'
        elif metric == 'Cash Conversion Cycle':
            prose += ' Longer cycles may increase funding needs; negative cycles can reflect collection before supplier payment.'
        else:
            prose += ' Evaluate alongside related metrics and industry conditions.'
        prose += f' Three-year assessment: {state["3-year direction"]}.'
    return MetricResult(metric, current, previous, current-previous, state['YoY change'],
                        state['3-year direction'], status, severity, prose)


def executive_summary(data: pd.DataFrame, risk_flags: list) -> dict[str, str]:
    row = data.iloc[-1]
    overview = f'FY{int(data.index[-1])} revenue is {display(row["Revenue"])} in reporting currency units.'
    if pd.notna(row['Revenue Growth']):
        overview += f' Revenue changed {row["Revenue Growth"]:.1%} versus the prior year.'
    result = {'Financial Overview': overview}
    for heading, metric in [('Profitability', 'Net Profit Margin'), ('Liquidity', 'Current Ratio'),
                             ('Solvency', 'Debt-to-Equity'), ('Efficiency', 'Cash Conversion Cycle'),
                             ('Cash Flow', 'Operating Cash Flow Margin')]:
        result[heading] = interpret(metric, data).interpretation
    result['Growth'] = 'Revenue growth: ' + display(row['Revenue Growth'], '%') + '. Conventional growth is unavailable when the prior base is nonpositive.'
    for heading, severities in [('Key Strengths', ['POSITIVE']), ('Key Risks', ['WARNING', 'HIGH RISK']),
                                ('Areas to Monitor', ['WATCH', 'INFO'])]:
        matching = [f.explanation for f in risk_flags if f.severity in severities]
        result[heading] = ' '.join(matching[:4]) or 'No available metric triggered a configured rule in this category.'
    return result
