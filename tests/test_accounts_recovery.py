import json
from pathlib import Path
import sqlite3
import pytest
import pandas as pd
from streamlit.testing.v1 import AppTest
from core.accounts import account_path
from data.database import Repository
from data.demo import demo_company, DEMO_META
from data.provenance import provenance_for_frame
from data.recovery import project_recovery, read_recovery


def test_account_identity_is_stable_and_isolated(tmp_path):
    claims = dict(is_logged_in=True, iss='https://issuer.example', sub='../alice', exp=500)
    alice = account_path(str(tmp_path), claims, now=100)
    assert alice.parent.parent == tmp_path
    assert alice == account_path(str(tmp_path), {**claims, 'email': 'changed@example.com'}, now=200)
    bob = account_path(str(tmp_path), {**claims, 'sub': 'bob'}, now=100)
    other = account_path(str(tmp_path), {**claims, 'iss': 'https://other.example'}, now=100)
    assert len({alice, bob, other}) == 3
    Repository(alice).save(DEMO_META, demo_company(), 'Private')
    assert len(Repository(alice).list_projects()) == 1
    assert Repository(bob).list_projects() == []


@pytest.mark.parametrize('change', [{'is_logged_in': False}, {'sub': ''}, {'iss': None},
                                     {'exp': 1}, {'exp': 'nan'}, {'exp': None}])
def test_invalid_accounts_cannot_resolve_storage(tmp_path, change):
    with pytest.raises(ValueError):
        account_path(str(tmp_path), dict(is_logged_in=True, iss='issuer', sub='alice', exp=500) | change,
                     now=100)


def test_account_mode_without_storage_stops_before_workspace(monkeypatch):
    monkeypatch.setenv('FALCON_FINALYSIS_ACCOUNTS', 'true')
    monkeypatch.delenv('FALCON_FINALYSIS_DATA_DIR', raising=False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    assert not app.exception
    assert any('storage is not configured' in error.value for error in app.error)
    assert not app.button


def test_project_recovery_roundtrip_and_separate_restore(tmp_path):
    frame = demo_company()
    sources = provenance_for_frame(frame, 'Fictional demo', 'Test')
    payload = project_recovery(DEMO_META, frame, 'Recovered', sources)
    meta, restored, name, restored_sources = read_recovery(payload)
    pd.testing.assert_frame_equal(frame, restored, check_dtype=False)
    pd.testing.assert_frame_equal(sources, restored_sources, check_dtype=False)
    repo = Repository(tmp_path / 'workspace.db')
    original = repo.save(meta, restored, name, provenance=restored_sources)
    copy = repo.save(meta, restored, name + ' (restored)', provenance=restored_sources)
    assert original != copy
    assert len(repo.list_projects()) == 2
    backup = tmp_path / 'restored.db'
    backup.write_bytes(repo.backup_bytes())
    with sqlite3.connect(backup) as con:
        assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert len(Repository(backup).list_projects()) == 2


@pytest.mark.parametrize('payload', [b'[]', b'null', b'{', b'{}', b'x' * (5 * 1024 * 1024 + 1)],
                         ids=['array', 'null', 'broken', 'empty', 'oversized'])
def test_bad_recovery_files_fail_with_guidance(payload):
    with pytest.raises(ValueError):
        read_recovery(payload)


def test_recovery_rejects_future_formats_and_invalid_financial_data():
    doc = json.loads(project_recovery(DEMO_META, demo_company(), 'Test'))
    doc['version'] = 9
    with pytest.raises(ValueError, match='version'):
        read_recovery(json.dumps(doc).encode())
    doc['version'] = 1
    doc['financial_data'][0]['Revenue'] = 'invalid'
    with pytest.raises(ValueError, match='finite'):
        read_recovery(json.dumps(doc).encode())
