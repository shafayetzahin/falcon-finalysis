"""Data-readiness explanations and persisted source lineage."""
import pandas as pd

from core.readiness import readiness
from core.config import FIELDS
from data.database import Repository
from data.demo import demo_company, DEMO_META
from data.provenance import provenance_for_frame, merge_provenance, changed_provenance


def test_readiness_explains_missing_fields():
    frame = pd.DataFrame({'Year': [2023, 2024, 2025], 'Revenue': [1, 2, 3],
                          'Net Income': [1, 1, 1]}).reindex(columns=['Year'] + FIELDS)
    result = readiness(frame).set_index('Analysis area')
    assert result.at['Performance overview', 'Status'] == 'Needs data'
    assert 'Operating Cash Flow' in result.at['Performance overview', 'Missing latest-year fields']
    assert result.at['Profitability', 'Coverage'] < 1


def test_provenance_merge_manual_change_and_repository_roundtrip(tmp_path):
    frame = demo_company()
    imported = provenance_for_frame(frame, 'Excel upload', 'demo.xlsx')
    edited = frame.copy()
    edited.loc[edited.index[-1], 'Revenue'] += 1
    manual = changed_provenance(frame, edited)
    combined = merge_provenance(imported, manual)
    latest = combined[(combined.Year == int(edited.Year.max())) & (combined.Field == 'Revenue')].iloc[0]
    assert latest['Source Type'] == 'Manual entry'

    repo = Repository(tmp_path / 'provenance.db')
    project_id = repo.save(DEMO_META, edited, 'Provenance test', provenance=combined)
    restored = repo.provenance(project_id)
    assert len(restored) == len(combined)
    assert set(restored['Source Type']) == {'Excel upload', 'Manual entry'}
