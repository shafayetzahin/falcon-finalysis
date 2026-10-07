"""Shared session data, headers and metric tiles."""
from pathlib import Path
from html import escape
import streamlit as st
import pandas as pd
from core.financial_engine import analyze
from core.config import AVERAGE_POLICY, DISCLAIMER
from core.ratio_engine import BY_NAME
from components.formatting import fmt, delta, unit_for
from components.charts import line_chart
from data.database import Repository


def hosted_mode() -> bool:
    """True when an administrator explicitly enables the public hosted profile."""
    import os
    return os.environ.get('FALCON_FINALYSIS_HOSTED', '').strip().lower() in {
        '1', 'true', 'yes', 'on'}


@st.cache_data(show_spinner=False, max_entries=25)
def cached_analysis(frame: pd.DataFrame, tolerance: float):
    return analyze(frame, tolerance)


def repository() -> Repository:
    import os
    from core.accounts import accounts_enabled, account_path
    if accounts_enabled():
        path = account_path(os.environ.get('FALCON_FINALYSIS_DATA_DIR', ''), st.user.to_dict())
        return Repository(path)
    if hosted_mode():
        import tempfile
        from uuid import uuid4
        if '_hosted_db_path' not in st.session_state:
            st.session_state['_hosted_db_path'] = str(
                Path(tempfile.gettempdir()) / f'falcon-finalysis-{uuid4().hex}.db')
        return Repository(Path(st.session_state['_hosted_db_path']))
    path = os.environ.get('FALCON_FINALYSIS_DB') or os.environ.get('FINSIGHT_DB')
    return Repository(Path(path)) if path else Repository()


def storage_notice() -> str:
    from core.accounts import accounts_enabled
    if accounts_enabled():
        return 'Saved work belongs to your signed-in account. Download recovery copies regularly.'
    if hosted_mode():
        return 'Temporary session: download a project recovery file before closing; server restarts can erase saved work.'
    return 'Saved work is stored on this device. Download recovery copies regularly.'


def reset_company_outputs() -> None:
    """Do not carry a previous company's review or editor changes into a new project."""
    for key in ('scenario', 'valuation_result', 'valuation_result_signature', 'pdf_bytes', 'xlsx_bytes',
                'report_fingerprint', 'statement_extraction', 'statement_extraction_key', 'import_report'):
        st.session_state.pop(key, None)
    st.session_state['project_generation'] = st.session_state.get('project_generation', 0) + 1
    for key in list(st.session_state):
        if key.startswith('driver_'):
            del st.session_state[key]


def require_analysis():
    from components.accounts import require_account
    require_account(show_controls=False)
    if 'frame' not in st.session_state:
        st.info('Load Demo Company from the sidebar, or create a company in Projects & Data.')
        st.stop()
    return cached_analysis(st.session_state.frame, st.session_state.get('tolerance', .01))


def header(title: str, subtitle: str) -> None:
    from components.accounts import require_account
    require_account(show_controls=False)
    st.caption('FALCON FINALYSIS  /  FINANCIAL ANALYTICS & DECISION SUPPORT')
    st.title(title)
    st.caption(subtitle)


def company_header(title: str) -> None:
    meta = st.session_state.get('meta', {})
    header(title, meta.get('company_name', 'Company analysis'))


def metrics(data: pd.DataFrame, names: list[str], columns: int = 4) -> None:
    currency = st.session_state.meta.get('currency', 'BDT')
    current, previous = data.iloc[-1], data.iloc[-2]
    for start in range(0, len(names), columns):
        cols = st.columns(columns)
        for col, name in zip(cols, names[start:start+columns]):
            unit = unit_for(name)
            explanation = BY_NAME[name].formula if name in BY_NAME else 'Reported annual value in full currency units.'
            with col:
                st.metric(name, fmt(current[name], unit, currency), delta(current[name], previous[name], unit),
                          delta_color='off', help=explanation, border=True)


def chart(df, names, title, unit='') -> None:
    st.plotly_chart(line_chart(df, names, title, unit, st.session_state.get('dark', False)),
                    width='stretch', config={'displaylogo': False})


def table(df: pd.DataFrame, percent: bool = False) -> None:
    st.dataframe(df.style.format('{:.1%}' if percent else '{:,.2f}', na_rep='N/A'), width='stretch')


def assumptions() -> None:
    with st.expander('Calculation assumptions and unavailable values'):
        st.write(AVERAGE_POLICY)
        st.write('N/A means required data is missing or a denominator is nonpositive. Zero is a reported value; blank is unavailable. Expense, capex and dividend inputs use positive magnitudes.')
        st.caption(DISCLAIMER)


def signal_card(flag) -> None:
    color = {'POSITIVE': '#147D64', 'WARNING': '#A56B13', 'HIGH RISK': '#B3424C', 'WATCH': '#A56B13'}.get(flag.severity, '#587089')
    with st.container(border=True):
        st.markdown(f'<span style="color:{color};font-size:11px;font-weight:700;letter-spacing:1px">{escape(flag.severity)}</span>', unsafe_allow_html=True)
        st.markdown('**' + flag.title + '**')
        st.write(flag.explanation)
        with st.expander('Evidence & questions to investigate'):
            st.caption(flag.metric + ' · values in native metric units')
            st.write(flag.trend)
            st.write(flag.questions)
