"""Three-factor DuPont and exact symmetric attribution of change in ROE."""
from itertools import permutations
import numpy as np
import pandas as pd


def dupont(frame: pd.DataFrame, ratios: pd.DataFrame) -> pd.DataFrame:
    df = frame.set_index('Year')
    assets = (df['Total Assets'] + df['Total Assets'].shift()) / 2
    equity = (df['Shareholders Equity'] + df['Shareholders Equity'].shift()) / 2
    assets.iloc[0], equity.iloc[0] = df['Total Assets'].iloc[0], df['Shareholders Equity'].iloc[0]
    valid = (equity > 0) & (assets > 0) & (df['Shareholders Equity'] > 0)
    valid &= (df['Shareholders Equity'].shift() > 0) | (df.index == df.index[0])
    out = ratios[['Net Profit Margin', 'Asset Turnover']].copy()
    out['Equity Multiplier'] = (assets/equity).where(valid)
    out['DuPont ROE'] = out.prod(axis=1, min_count=3)
    return out


def attribution(table: pd.DataFrame) -> pd.Series:
    """Shapley allocation averages all six factor orders; contributions sum to ROE change."""
    names = ['Net Profit Margin', 'Asset Turnover', 'Equity Multiplier']
    if len(table) < 2 or table[names].tail(2).isna().any().any():
        return pd.Series(np.nan, index=names)
    old, new = table[names].iloc[-2].values, table[names].iloc[-1].values
    contributions = np.zeros(3)
    for order in permutations(range(3)):
        state = old.copy()
        for i in order:
            before = np.prod(state)
            state[i] = new[i]
            contributions[i] += (np.prod(state) - before) / 6
    return pd.Series(contributions, index=names)
