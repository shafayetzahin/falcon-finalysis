"""Transparent, generic Falcon Finalysis score with explicit missing-data coverage."""
from dataclasses import dataclass
import numpy as np
import pandas as pd

# (metric, low threshold, high threshold, lower is better)
POLICY = {
    'Liquidity': (20, [('Current Ratio', .5, 2, False), ('Quick Ratio', .25, 1.5, False)]),
    'Profitability': (20, [('Net Profit Margin', 0, .15, False), ('ROA', 0, .1, False)]),
    'Leverage/Solvency': (20, [('Debt-to-Equity', 0, 2, True), ('Interest Coverage', 1, 6, False)]),
    'Efficiency': (15, [('Asset Turnover', .2, 1.5, False), ('Cash Conversion Cycle', 0, 150, True)]),
    'Cash Flow': (15, [('Operating Cash Flow Margin', 0, .2, False), ('Cash Flow to Net Income', 0, 1.5, False)]),
    'Growth/Stability': (10, [('Revenue Growth', -.1, .15, False), ('Revenue Stability', 0, .3, True)]),
}


@dataclass
class HealthScore:
    score: float | None
    label: str
    coverage: float
    categories: pd.DataFrame


def health_score(row: pd.Series) -> HealthScore:
    """Linear interpolation within published bounds; unavailable inputs earn no hidden points."""
    categories, earned, possible = [], 0., 0.
    for name, (weight, rules) in POLICY.items():
        scores = []
        for metric, low, high, inverse in rules:
            value = row.get(metric, np.nan)
            if pd.notna(value) and np.isfinite(value):
                scaled = float(np.clip((value - low) / (high-low), 0, 1))
                scores.append(1-scaled if inverse else scaled)
        coverage = len(scores)/len(rules)
        normalized = float(np.mean(scores)*100) if scores else np.nan
        points = sum(scores)*weight/len(rules)
        earned += points
        possible += weight*coverage
        categories.append({'Category': name, 'Weight': weight, 'Score / 100': normalized,
                           'Points earned': points, 'Available points': weight*coverage, 'Coverage': coverage})
    complete_categories = all(c['Coverage'] > 0 for c in categories)
    score = round(100*earned/possible, 1) if possible >= 75 and complete_categories else None
    label = 'Insufficient data'
    if score is not None:
        label = next(text for bound, text in [(85, 'Strong'), (70, 'Healthy'), (55, 'Moderate'),
                                             (40, 'Weak'), (0, 'High Financial Risk')] if score >= bound)
    return HealthScore(score, label, possible/100, pd.DataFrame(categories))
