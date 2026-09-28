"""Human-readable values, units and financial deltas."""
import numpy as np
import pandas as pd
from core.config import CURRENCIES
from core.ratio_engine import BY_NAME


def unit_for(metric: str) -> str:
    if metric in BY_NAME:
        return BY_NAME[metric].unit
    if metric in ['Revenue Growth', 'Net Margin', 'ROA', 'ROE']:
        return '%'
    return 'money'


def fmt(value: float, unit: str = 'money', currency: str = 'BDT', compact: bool = True) -> str:
    if value is None or pd.isna(value) or not np.isfinite(value):
        return 'N/A'
    if unit == '%':
        return f'{value:.1%}'
    if unit == 'x':
        return f'{value:.2f}x'
    if unit == 'days':
        return f'{value:.1f} days'
    prefix = CURRENCIES.get(currency, currency + ' ') if unit == 'money' else ''
    if unit == 'money' and currency == 'BDT':
        try:
            import streamlit as st
            scale = st.session_state.get('number_scale', 'Automatic')
        except Exception:
            scale = 'Automatic'
        if scale == 'Lakh':
            return f'{prefix}{value/100_000:,.2f} lakh'
        if scale == 'Crore':
            return f'{prefix}{value/10_000_000:,.2f} crore'
    if compact:
        for divisor, suffix in [(1e9, 'B'), (1e6, 'M'), (1e3, 'K')]:
            if abs(value) >= divisor:
                return f'{prefix}{value/divisor:,.2f}{suffix}'
    return f'{prefix}{value:,.2f}'


def delta(current: float, previous: float, unit: str) -> str | None:
    if pd.isna(current) or pd.isna(previous):
        return None
    if unit == '%':
        change = round((current-previous)*100, 1)
        return '0.0 pp' if change == 0 else f'{change:+.1f} pp'
    if unit in ['x', 'days']:
        return f'{current-previous:+.2f} {unit}'
    return f'{(current/previous-1):+.1%}' if previous > 0 else None
