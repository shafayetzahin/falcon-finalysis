"""Year-on-year, base-year, common-size and multi-period trend analysis."""
import numpy as np
import pandas as pd
from core.config import INCOME, BALANCE


def growth(series: pd.Series) -> pd.Series:
    """Conventional growth requires a positive prior base; never forward-fill gaps."""
    previous = series.shift()
    return ((series - previous) / previous).where(previous > 0).replace([np.inf, -np.inf], np.nan)


def cagr(series: pd.Series) -> float:
    """Positive endpoints over at least three observations, using elapsed fiscal years."""
    if len(series) < 3 or series.isna().any() or series.iloc[0] <= 0 or series.iloc[-1] <= 0:
        return np.nan
    years = int(series.index[-1]) - int(series.index[0])
    return float((series.iloc[-1] / series.iloc[0]) ** (1 / years) - 1) if years > 0 else np.nan


def horizontal(df: pd.DataFrame, base_year: int) -> pd.DataFrame:
    base = df.loc[base_year]
    rows = []
    for year, row in df.iterrows():
        for metric, value in row.items():
            b = base[metric]
            rows.append({'Year': year, 'Metric': metric, 'Value': value, 'Absolute change': value-b,
                         'Percentage change': (value-b)/b if b > 0 else np.nan})
    return pd.DataFrame(rows)


def vertical(df: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=df.index)
    for col in INCOME + BALANCE:
        denominator = df['Revenue'] if col in INCOME else df['Total Assets']
        result[col] = df[col].div(denominator.where(denominator > 0))
    return result


LOWER_BETTER = {'Debt-to-Equity', 'Liabilities-to-Equity', 'Debt Ratio', 'Inventory Days',
                'Receivable Days', 'Cash Conversion Cycle'}


def describe(series: pd.Series, lower_better: bool = False) -> dict:
    """Classify the last three annual observations, requiring both movements to agree."""
    tail = series.tail(3)
    direction, volatility = 'Insufficient history', np.nan
    if len(tail) == 3 and tail.notna().all():
        scale = max(abs(tail.iloc[0]), abs(tail.mean()), 1e-9)
        steps = tail.diff().dropna() / scale
        signed = steps * (-1 if lower_better else 1)
        total = signed.sum()
        if (signed > 0.005).all():
            direction = 'Strong Improvement' if total >= .2 else 'Improving'
        elif (signed < -.005).all():
            direction = 'Strong Deterioration' if total <= -.2 else 'Deteriorating'
        else:
            direction = 'Stable' if abs(total) < .05 else 'Mixed trend'
        volatility = float(tail.std(ddof=0) / max(abs(tail.mean()), 1e-9))
    return {'Current': series.iloc[-1], 'Previous': series.iloc[-2] if len(series) > 1 else np.nan,
            'YoY change': growth(series).iloc[-1], '3-year direction': direction,
            'Volatility': volatility}
