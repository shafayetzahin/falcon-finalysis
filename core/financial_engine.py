"""Single analysis service shared by UI, database snapshots and reporting."""
from dataclasses import dataclass
import pandas as pd
from core.config import FIELDS
from core.validation import validate
from core.ratio_engine import calculate
from core.trend_engine import growth, cagr, describe, LOWER_BETTER, vertical
from core.dupont_engine import dupont
from core.health_score import health_score
from core.risk_engine import flags
from core.interpretation_engine import executive_summary


@dataclass
class Analysis:
    statements: pd.DataFrame
    ratios: pd.DataFrame
    reasons: pd.DataFrame
    combined: pd.DataFrame
    growth: pd.DataFrame
    cagr: pd.Series
    dupont: pd.DataFrame
    health: list
    flags: list
    summary: dict
    trends: pd.DataFrame
    vertical: pd.DataFrame
    issues: list


def analyze(frame: pd.DataFrame, tolerance: float = .01) -> Analysis:
    issues = validate(frame, tolerance)
    errors = [x.message for x in issues if x.severity == 'ERROR']
    if errors:
        raise ValueError(' '.join(errors))
    frame = frame.reindex(columns=['Year'] + FIELDS).sort_values('Year').copy()
    ratios, reasons = calculate(frame)
    statements = frame.set_index('Year').astype(float)
    combined = pd.concat([statements, ratios], axis=1)
    keys = ['Revenue', 'Gross Profit', 'EBITDA', 'EBIT', 'Net Income', 'EPS', 'Total Assets',
            'Shareholders Equity', 'Total Debt', 'Operating Cash Flow', 'Free Cash Flow']
    changes = combined[keys].apply(growth)
    combined['Revenue Growth'] = changes['Revenue']
    # Three-observation annual-growth variability; no optimistic filling for early history.
    combined['Revenue Stability'] = changes['Revenue'].rolling(2, min_periods=2).std(ddof=0)
    health = [health_score(row) for _, row in combined.iterrows()]
    signals = flags(combined)
    trends = pd.DataFrame({k: describe(combined[k], k in LOWER_BETTER) for k in keys + list(ratios.columns)}).T
    return Analysis(statements, ratios, reasons, combined, changes,
                    pd.Series({k: cagr(combined[k]) for k in keys}), dupont(frame, ratios), health,
                    signals, executive_summary(combined, signals), trends, vertical(statements), issues)
