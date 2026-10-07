"""End-to-end regressions for reviewed inputs and stale decision outputs."""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv('FALCON_FINALYSIS_DB', str(tmp_path / 'ui-audit.db'))
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    next(button for button in at.button if button.label == 'Try a complete demo').click().run()
    at.run()
    assert not at.exception and not at.error
    assert 'Apex' in at.title[0].value
    return at


def test_valuation_requires_review_and_invalidates_changed_assumptions(workspace):
    at = workspace.switch_page('pages/valuation.py').run()
    calculate = next(button for button in at.button if button.label == 'Calculate valuation range')
    assert calculate.disabled
    next(field for field in at.checkbox if field.label.startswith('I verified shares')).check().run()
    next(field for field in at.text_input if field.label == 'Market assumptions source and as-of date').set_value('Reviewed demo assumptions').run()
    next(button for button in at.button if button.label == 'Calculate valuation range').click().run()
    assert any(metric.label == 'DCF value per share' for metric in at.metric)
    next(field for field in at.number_input if field.label == 'Reviewed beta').set_value(1.5).run()
    assert not any(metric.label == 'DCF value per share' for metric in at.metric)
    assert any('Valuation inputs changed' in item.value for item in at.info)
    assert not at.exception and not at.error


def test_portfolio_changed_rate_removes_old_report(workspace):
    at = workspace.switch_page('pages/portfolio.py').run()
    next(button for button in at.button if button.label == 'Load fictional sample portfolio').click().run()
    next(button for button in at.button if button.label == 'Calculate portfolio return and risk').click().run()
    assert any(button.label == 'Download reviewable portfolio report' for button in at.download_button)
    next(field for field in at.number_input if field.label == 'Annual risk-free reference rate %').set_value(12.).run()
    assert not any(button.label == 'Download reviewable portfolio report' for button in at.download_button)
    assert any('Portfolio inputs changed' in item.value for item in at.info)
    assert not at.exception and not at.error


def test_credit_consent_withdrawal_removes_score_and_export(workspace):
    at = workspace.switch_page('pages/credgrid.py').run()
    next(button for button in at.button if button.label == 'Load fictional CredGrid case').click().run()
    next(button for button in at.button if button.label == 'Calculate explainable credit analysis').click().run()
    assert any(metric.label == 'CredGrid score' for metric in at.metric)
    next(button for button in at.button if button.label == 'Save credit case').click().run()
    assert any(field.label == 'Human decision' for field in at.selectbox)
    next(field for field in at.checkbox if field.label.startswith('The applicant consented')).uncheck().run()
    assert not any(metric.label == 'CredGrid score' for metric in at.metric)
    assert not any(button.label == 'Download reviewer report' for button in at.download_button)
    assert not any(field.label == 'Human decision' for field in at.selectbox)
    assert next(button for button in at.button if button.label == 'Calculate explainable credit analysis').disabled
    assert not at.exception and not at.error


def test_credit_identity_change_requires_recalculation(workspace):
    at = workspace.switch_page('pages/credgrid.py').run()
    next(button for button in at.button if button.label == 'Load fictional CredGrid case').click().run()
    next(button for button in at.button if button.label == 'Calculate explainable credit analysis').click().run()
    next(field for field in at.text_input if field.label == 'Business type').set_value('Changed business activity').run()
    assert not any(metric.label == 'Modeled amount' for metric in at.metric)
    assert not at.exception and not at.error


def test_comparison_selection_does_not_show_previous_companies(workspace):
    at = workspace.switch_page('pages/industry_comparison.py').run()
    # Model an already fetched set without depending on exchange availability.
    at.session_state['industry_exchange_key'] = ('DSE', ('OLDCO', 'PEER'))
    at.session_state['industry_exchange_details'] = {
        'OLDCO': pd.DataFrame({'Year': [2025], 'Exchange metric': ['Basic EPS'], 'Value': [10.]})}
    at.session_state['industry_exchange_sources'] = {'OLDCO': {'source': 'old source'}}
    at.run()
    assert 'industry_exchange_details' not in at.session_state
    assert any('comparison set changed' in item.value.lower() for item in at.info)
    assert not at.exception and not at.error


def test_loading_new_portfolio_resets_old_holding_edits(workspace):
    at = workspace.switch_page('pages/portfolio.py').run()
    next(button for button in at.button if button.label == 'Load fictional sample portfolio').click().run()
    generation = at.session_state['portfolio_generation']
    at.session_state[f'portfolio_holding_editor_{generation}'] = {
        'edited_rows': {0: {'Initial Shares': 99.}}, 'added_rows': [], 'deleted_rows': []}
    at.run()
    assert at.session_state['portfolio_holdings'].iloc[0]['Initial Shares'] == 99.
    next(button for button in at.button if button.label == 'Load fictional sample portfolio').click().run()
    assert at.session_state['portfolio_holdings'].iloc[0]['Initial Shares'] == 1.
    assert at.session_state['portfolio_generation'] > generation
    assert not at.exception and not at.error


def test_credit_decision_requires_confirmation_on_submission(workspace):
    at = workspace.switch_page('pages/credgrid.py').run()
    next(button for button in at.button if button.label == 'Load fictional CredGrid case').click().run()
    next(button for button in at.button if button.label == 'Calculate explainable credit analysis').click().run()
    next(button for button in at.button if button.label == 'Save credit case').click().run()
    submit = next(button for button in at.button if button.label == 'Record final human decision')
    assert not submit.disabled
    submit.click().run()
    assert any('Confirm your review' in error.value for error in at.error)
    assert not at.exception


def test_new_company_requires_fresh_valuation_confirmation(workspace):
    at = workspace.switch_page('pages/valuation.py').run()
    next(field for field in at.checkbox if field.label.startswith('I verified shares')).check().run()
    at.session_state['project_generation'] += 1
    at.run()
    assert not next(field for field in at.checkbox if field.label.startswith('I verified shares')).value
    assert next(button for button in at.button if button.label == 'Calculate valuation range').disabled
