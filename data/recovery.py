"""Portable, data-only recovery for financial project inputs and source references."""
import json
import pandas as pd
from core.config import FIELDS
from core.validation import validate
from data.provenance import PROVENANCE_COLUMNS

META_FIELDS = ('company_name', 'industry', 'currency', 'country', 'description')


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Recovery file contains duplicate JSON fields.')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Recovery file must use valid JSON numbers; leave unavailable values null.')


def read_recovery(payload: bytes) -> tuple[dict, pd.DataFrame, str, pd.DataFrame]:
    if not payload or len(payload) > 5 * 1024 * 1024:
        raise ValueError('Use a non-empty recovery file smaller than 5 MB.')
    try:
        doc = json.loads(payload, object_pairs_hook=_json_object, parse_constant=_invalid_constant)
        if not isinstance(doc, dict):
            raise ValueError('Recovery file must contain a project object.')
        if doc['format'] != 'falcon-financial-project' or type(doc['version']) is not int or doc['version'] != 1:
            raise ValueError('Unsupported recovery format or version.')
        if not isinstance(doc['company'], dict):
            raise ValueError('Recovery company details must be an object.')
        meta = {key: doc['company'].get(key, '') for key in META_FIELDS}
        name = doc['name']
        if not all(isinstance(v, str) and len(v) <= 2000 for v in [*meta.values(), name]):
            raise ValueError('Recovery names and company details must be text of at most 2,000 characters.')
        for value in [*meta.values(), name]:
            value.encode('utf-8')
        if not name.strip() or not meta['company_name'].strip():
            raise ValueError('Recovery file needs company and project names.')
        records = doc['financial_data']
        if not isinstance(records, list) or not 3 <= len(records) <= 10 or not all(
                isinstance(row, dict) for row in records):
            raise ValueError('Recovery financial data must contain 3–10 annual records.')
        for row in records:
            for value in row.values():
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                    raise ValueError('Recovery financial values must be finite numbers or null.')
        frame = pd.DataFrame(records)
        if set(frame.columns) - set(['Year'] + FIELDS):
            raise ValueError('Recovery file contains unrecognized financial fields.')
        errors = [issue.message for issue in validate(frame) if issue.severity == 'ERROR']
        if errors:
            raise ValueError(' '.join(errors))
        frame = frame.reindex(columns=['Year'] + FIELDS)
        frame = frame.apply(pd.to_numeric, errors='raise')
        source_records = doc.get('provenance', [])
        if not isinstance(source_records, list) or len(source_records) > 2000 or not all(
                isinstance(row, dict) and set(row) == set(PROVENANCE_COLUMNS) for row in source_records):
            raise ValueError('Invalid recovery source references.')
        sources = pd.DataFrame(source_records, columns=PROVENANCE_COLUMNS)
        if not sources.empty:
            if len(sources) > 2000 or sources.isna().any().any():
                raise ValueError('Invalid recovery source references.')
            sources['Year'] = pd.to_numeric(sources['Year'], errors='raise')
            if sources.duplicated(['Year', 'Field']).any():
                raise ValueError('Recovery contains conflicting source references for the same value.')
            if not sources['Year'].isin(frame.Year).all() or not sources['Field'].isin(FIELDS).all():
                raise ValueError('Source references must match the recovered years and fields.')
            for col in PROVENANCE_COLUMNS[1:]:
                if not sources[col].map(lambda x: isinstance(x, str) and len(x) <= 4000).all():
                    raise ValueError('Invalid recovery source text.')
                for value in sources[col]:
                    value.encode('utf-8')
        return meta, frame, name, sources
    except json.JSONDecodeError as exc:
        raise ValueError('This is not a valid Falcon Finalysis project recovery file.') from exc
    except (KeyError, TypeError, AttributeError, UnicodeError, OverflowError, RecursionError) as exc:
        raise ValueError('This is not a valid Falcon Finalysis project recovery file.') from exc


def project_recovery(meta: dict, frame: pd.DataFrame, name: str, provenance=None) -> bytes:
    doc = {'format': 'falcon-financial-project', 'version': 1, 'name': name,
           'company': {key: meta.get(key, '') for key in META_FIELDS},
           'financial_data': json.loads(frame.to_json(orient='records')),
           'provenance': json.loads(provenance.to_json(orient='records'))
           if isinstance(provenance, pd.DataFrame) else []}
    payload = json.dumps(doc, ensure_ascii=False, allow_nan=False).encode('utf-8')
    read_recovery(payload)
    return payload
