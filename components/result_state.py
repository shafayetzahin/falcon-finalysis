"""Match saved analytical results to the exact inputs currently under review."""
from datetime import date, datetime
import hashlib
import json

import pandas as pd


def input_signature(*values) -> str:
    def encode(value):
        if isinstance(value, (pd.DataFrame, pd.Series)):
            return {'table': value.to_json(orient='split', date_format='iso', double_precision=15)}
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        raise TypeError(f'Unsupported analysis input: {type(value).__name__}')
    payload = json.dumps(values, default=encode, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def discard_changed_result(state, result_key: str, signature: str) -> bool:
    if result_key in state and state.get(result_key + '_signature') != signature:
        state.pop(result_key, None)
        state.pop(result_key + '_signature', None)
        return True
    return False


def stable_editor_base(state, widget_key: str, latest: pd.DataFrame) -> pd.DataFrame:
    """Apply widget deltas to one base; preserve reviewed values across page visits."""
    base_key = widget_key + '_base'
    if widget_key not in state or base_key not in state:
        state[base_key] = latest.copy(deep=True)
    return state[base_key]
