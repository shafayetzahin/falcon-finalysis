"""Bounded CSV/XLSX input and configurable financial-label mapping."""
from io import BytesIO
from pathlib import Path
import re
import zipfile
import pandas as pd
from openpyxl import load_workbook
from core.config import ALIASES, FIELDS
from core.validation import validate


def normalize(label: str) -> str:
    return re.sub(r'[^a-z0-9]', '', str(label).lower())


def suggest_mapping(columns: list, extra: dict | None = None) -> dict[str, str]:
    lookup = {normalize(c): c for c in ['Year'] + FIELDS}
    for target, aliases in ALIASES.items():
        lookup.update({normalize(a): target for a in aliases})
    lookup.update({normalize(k): v for k, v in (extra or {}).items()})
    return {str(c): lookup.get(normalize(c), 'Ignore') for c in columns}


def read_file(payload: bytes, filename: str, sheet: str | None = None) -> pd.DataFrame:
    """Read raw tabular data. Reject formulas rather than execute or trust cached results."""
    if not payload:
        raise ValueError('The uploaded file is empty.')
    if len(payload) > 10 * 1024 * 1024:
        raise ValueError('Upload a file smaller than 10 MB.')
    ext = Path(filename).suffix.lower()
    try:
        if ext == '.csv':
            df = pd.read_csv(BytesIO(payload), nrows=101, encoding='utf-8-sig')
        elif ext == '.xlsx':
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                if sum(x.file_size for x in archive.infolist()) > 50 * 1024 * 1024:
                    raise ValueError('The expanded workbook is too large (50 MB limit).')
            book = load_workbook(BytesIO(payload), read_only=True, data_only=False, keep_links=False)
            try:
                ws = book[sheet] if sheet else book.active
                if ws.max_row and ws.max_row > 101 or ws.max_column and ws.max_column > 100:
                    raise ValueError('Use a compact table: at most 100 rows and 100 columns.')
                rows = []
                for row in ws.iter_rows():
                    if any(cell.data_type == 'f' for cell in row):
                        raise ValueError('Formula cells are not accepted. Paste values into a copy before upload.')
                    rows.append([cell.value for cell in row])
                if not rows:
                    raise ValueError('This worksheet is empty.')
                if len(rows[0]) != len(set(rows[0])):
                    raise ValueError('Use unique column headers.')
                df = pd.DataFrame(rows[1:], columns=rows[0]).dropna(how='all')
            finally:
                book.close()
        else:
            raise ValueError('Use .xlsx or UTF-8 .csv. Convert legacy .xls files to .xlsx first.')
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('Unable to read this file. Check its format and use the downloadable template.') from exc
    if df.empty:
        raise ValueError('The file contains no data rows.')
    if len(df) > 100 or len(df.columns) > 100:
        raise ValueError('Use at most 100 rows and 100 columns.')
    return df


def prepare(raw: pd.DataFrame, mapping: dict | None = None) -> pd.DataFrame:
    """Apply user-reviewed mappings; do not infer subtotals or replace missing amounts."""
    mapping = mapping or suggest_mapping(list(raw.columns))
    selected = {k: v for k, v in mapping.items() if v != 'Ignore'}
    if len(selected.values()) != len(set(selected.values())):
        raise ValueError('Two columns map to the same field. Assign one or ignore the duplicate.')
    if any(v not in ['Year'] + FIELDS for v in selected.values()):
        raise ValueError('Mapping contains an unknown financial field.')
    df = raw[list(selected)].rename(columns=selected).copy()
    for col in df:
        # Commas and accounting parentheses are common values-only export conventions.
        text = df[col].astype('string').str.strip().str.replace(',', '', regex=False)
        text = text.str.replace(r'^\((.*)\)$', r'-\1', regex=True)
        numeric = pd.to_numeric(text.replace('', pd.NA), errors='coerce')
        if (text.notna() & text.ne('') & numeric.isna()).any():
            raise ValueError(f'{col} contains text or formulas. Use numbers, or blank for unavailable data.')
        df[col] = numeric.astype(float)
    errors = [x.message for x in validate(df) if x.severity == 'ERROR']
    if errors:
        raise ValueError(' '.join(errors))
    df['Year'] = df['Year'].astype(int)
    return df.reindex(columns=['Year'] + FIELDS).sort_values('Year').reset_index(drop=True)
