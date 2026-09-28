"""Evidence-based strengths, risks and analytical questions."""
from dataclasses import dataclass, asdict
import pandas as pd


@dataclass
class Flag:
    title: str
    metric: str
    value: float
    trend: str
    severity: str
    explanation: str
    questions: str

    def to_dict(self) -> dict:
        return asdict(self)


def flags(data: pd.DataFrame) -> list[Flag]:
    """Generic thresholds generate investigation prompts, never investment recommendations."""
    out: list[Flag] = []
    now, prev = data.iloc[-1], data.iloc[-2]

    def emit(title: str, metric: str, severity: str, explanation: str, questions: str) -> None:
        series = data[metric].tail(3)
        trend = '; '.join(f'{int(y)}: {v:,.2f}' for y, v in series.items() if pd.notna(v))
        out.append(Flag(title, metric, float(now[metric]), trend, severity, explanation, questions))

    rules = [
        ('Current Ratio', 1, 'WARNING', 'Short-term liquidity constrained', 'Current assets are below current liabilities. This may constrain short-term payment capacity.', 'What obligations fall due soon? Are committed credit lines available?'),
        ('Quick Ratio', .75, 'WATCH', 'Limited liquid asset coverage', 'Liquid current assets cover less than 0.75 times current liabilities.', 'How readily can inventory be converted into cash?'),
        ('Net Working Capital', 0, 'WARNING', 'Negative working capital', 'Current liabilities exceed current assets; the operating model and cash cycle warrant review.', 'Is negative working capital structural or a recent change?'),
        ('Interest Coverage', 2, 'WARNING', 'Interest coverage narrowing', 'Operating earnings provide limited coverage of interest expense.', 'When does debt reprice? How much earnings headroom remains?'),
        ('Operating Margin', 0, 'HIGH RISK', 'Operating loss', 'Reported EBIT is negative, suggesting operations did not cover operating costs.', 'Which costs or revenue changes explain the loss?'),
        ('Net Profit Margin', 0, 'HIGH RISK', 'Net loss', 'Reported net income is negative.', 'Are losses recurring or driven by exceptional items?'),
        ('Operating Cash Flow', 0, 'WARNING', 'Negative operating cash flow', 'Operations consumed cash during the latest year.', 'Did working capital absorb cash? Were there unusual payments?'),
        ('Revenue Growth', 0, 'WATCH', 'Revenue contracted', 'Revenue declined from a positive prior-year base.', 'Did volumes, prices or the product mix change?'),
    ]
    for metric, cutoff, severity, title, explanation, questions in rules:
        if now[metric] < cutoff:
            if metric == 'Interest Coverage' and now[metric] < 1:
                severity = 'HIGH RISK'
                explanation = 'EBIT does not cover interest expense, suggesting limited earnings protection.'
            emit(title, metric, severity, explanation, questions)
    if now['Net Income'] > 0 and now['Operating Cash Flow'] < 0:
        emit('Profit without operating cash', 'Operating Cash Flow', 'HIGH RISK',
             'Profitability is positive, but operating cash flow is negative. This may indicate weaker earnings-to-cash conversion and warrants investigation.',
             'Are receivables collectible? Are noncash gains material?')
    if (data['Free Cash Flow'].tail(2) < 0).all():
        emit('Repeated negative free cash flow', 'Free Cash Flow', 'WARNING',
             'Free cash flow was negative in both latest years. Growth investment could explain part of the funding need.', 'Is capex discretionary? How is the shortfall financed?')
    if (data['Net Profit Margin'].tail(3).diff().dropna() < 0).all() and data['Net Profit Margin'].tail(3).notna().all():
        emit('Margin compression across three years', 'Net Profit Margin', 'WATCH',
             'Net margin declined across the latest three annual observations, suggesting persistent earnings pressure.', 'Are input costs, overhead or financing costs rising?')
    for metric, title in [('Receivable Days', 'Receivable collection slowing'), ('Inventory Days', 'Inventory holding period rising'),
                          ('Cash Conversion Cycle', 'Cash tied up for longer')]:
        if now[metric] - prev[metric] > 5:
            emit(title, metric, 'WARNING', f'{metric} increased by more than five days in the latest year. This may increase operating funding needs.',
                 'Did terms or customer quality change? Is inventory moving more slowly?')
    if now['Payable Days'] - prev['Payable Days'] < -5:
        emit('Supplier payment period shortening', 'Payable Days', 'WATCH', 'Payable days declined by more than five days, potentially reducing supplier financing.', 'Have suppliers tightened terms? Were early-payment discounts obtained?')
    if data['Cash Conversion Cycle'].tail(3).notna().all() and (data['Cash Conversion Cycle'].tail(3).diff().dropna() > 0).all():
        emit('Cash cycle worsening over three years', 'Cash Conversion Cycle', 'WATCH', 'The cash conversion cycle lengthened in both latest annual movements.', 'What collection and stock targets could release cash?')
    if now['Debt-to-Equity'] - prev['Debt-to-Equity'] > .15:
        emit('Leverage increasing materially', 'Debt-to-Equity', 'WARNING', 'Debt-to-equity increased by more than 0.15 times.', 'What is the borrowing funding? Are covenants affected?')
    if now['Net Income'] < prev['Net Income']:
        emit('Earnings declined', 'Net Income', 'WATCH', 'Net income is lower than the prior year.', 'What explains the earnings bridge?')
    if now['Revenue'] > prev['Revenue'] and now['Operating Cash Flow'] < prev['Operating Cash Flow']:
        emit('Sales and cash flow diverge', 'Operating Cash Flow', 'WATCH', 'Sales increased while operating cash flow declined.', 'Is growth consuming additional working capital?')
    lg = (now['Total Liabilities']/prev['Total Liabilities']-1) if prev['Total Liabilities'] > 0 else float('nan')
    for denominator in ['Total Assets', 'Shareholders Equity']:
        comparison = now[denominator]/prev[denominator]-1 if prev[denominator] > 0 else float('nan')
        if lg - comparison > .10:
            emit('Liabilities outpace ' + denominator.lower(), 'Total Liabilities', 'WATCH',
                 f'Liability growth exceeds {denominator.lower()} growth by over ten percentage points.', 'Is financing supporting productive assets or covering losses?')
    for metric, title, better in [('Operating Cash Flow', 'Operating cash flow improved', 1),
                                  ('Net Profit Margin', 'Net margin improved', 1), ('Debt-to-Equity', 'Leverage declined', -1),
                                  ('Cash Conversion Cycle', 'Cash cycle shortened', -1), ('ROA', 'Asset returns improved', 1),
                                  ('Interest Coverage', 'Interest protection improved', 1)]:
        if (now[metric]-prev[metric])*better > 0 and (better == -1 or now[metric] > 0):
            emit(title, metric, 'POSITIVE', f'{metric} moved in a potentially favorable direction versus the previous year.', 'Is this improvement recurring and sustainable?')
    if now['ROE'] > prev['ROE'] and now['Debt-to-Equity'] <= prev['Debt-to-Equity'] + .05:
        emit('Equity returns improved with stable leverage', 'ROE', 'POSITIVE', 'ROE rose without debt-to-equity increasing by more than 0.05 times.', 'Which operating factors explain the improvement?')
    if data['Revenue'].tail(3).notna().all() and (data['Revenue'].tail(3).diff().dropna() > 0).all():
        emit('Consistent revenue growth', 'Revenue', 'POSITIVE', 'Revenue grew in both latest annual intervals.', 'Is growth supported by volume, pricing or acquisitions?')
    if not out:
        out.append(Flag('No configured rule triggered', 'Coverage', 0, '', 'INFO',
                        'No available metric triggered these generic rules. This does not establish an absence of risk.', 'Are all relevant inputs available?'))
    return out
