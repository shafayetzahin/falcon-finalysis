"""Portable, data-only recovery for financial project inputs and source references."""
import json
import pandas as pd
from core.config import FIELDS
from core.validation import validate
from data.provenance import PROVENANCE_COLUMNS

META_FIELDS = ('company_name', 'industry', 'currency', 'country', 'description')


def read_recovery(payload: bytes) -> tuple[dict, pd.DataFrame, str, pd.DataFrame]:
    if not payload or len(payload) > 5 * 1024 * 1024:
        raise ValueError('Use a non-empty recovery file smaller than 5 MB.')
    try:
        doc = json.loads(payload)
        if doc['format'] != 'falcon-financial-project' or doc['version'] != 1:
            raise ValueError('Unsupported recovery format or version.')
        meta = {key: doc['company'].get(key, '') for key in META_FIELDS}
        name = doc['name']
        if not all(isinstance(v, str) and len(v) <= 2000 for v in [*meta.values(), name]):
            raise ValueError('Recovery names and company details must be text of at most 2,000 characters.')
        if not name.strip() or not meta['company_name'].strip():
            raise ValueError('Recovery file needs company and project names.')
        frame = pd.DataFrame(doc['financial_data'])
        if set(frame.columns) - set(['Year'] + FIELDS):
            raise ValueError('Recovery file contains unrecognized financial fields.')
        errors = [issue.message for issue in validate(frame) if issue.severity == 'ERROR']
        if errors:
            raise ValueError(' '.join(errors))
        frame = frame.reindex(columns=['Year'] + FIELDS)
        frame = frame.apply(pd.to_numeric, errors='raise')
        sources = pd.DataFrame(doc.get('provenance', []), columns=PROVENANCE_COLUMNS)
        if not sources.empty:
            if len(sources) > 2000 or sources.isna().any().any():
                raise ValueError('Invalid recovery source references.')
            sources['Year'] = pd.to_numeric(sources['Year'], errors='raise')
            if not sources['Year'].isin(frame.Year).all() or not sources['Field'].isin(FIELDS).all():
                raise ValueError('Source references must match the recovered years and fields.')
            for col in PROVENANCE_COLUMNS[1:]:
                if not sources[col].map(lambda x: isinstance(x, str) and len(x) <= 4000).all():
                    raise ValueError('Invalid recovery source text.')
        return meta, frame, name, sources
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
