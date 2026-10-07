"""Falcon Finalysis local application entry point: python -m streamlit run app.py."""
from pathlib import Path
import logging
import streamlit as st
from data.demo import demo_company, DEMO_META
from data.provenance import provenance_for_frame
from components.ui import hosted_mode, repository, storage_notice, reset_company_outputs
from components.accounts import require_account
from core.i18n import nav_label, workflow_guide

ROOT = Path(__file__).resolve().parent
ACTIVE_LOGO = ROOT / 'assets' / 'logo-active.png'
HOSTED_MODE = hosted_mode()
logging.basicConfig(filename=ROOT/'falcon_finalysis.log', level=logging.WARNING,
                    format='%(asctime)s %(levelname)s %(message)s')
st.set_page_config(page_title='Falcon Finalysis | Financial Analytics', page_icon='◈', layout='wide')
require_account()
st.markdown((ROOT/'assets/styles.css').read_text(), unsafe_allow_html=True)


@st.dialog('Important decision-support notice', width='large')
def decision_support_notice() -> None:
    st.markdown('''
**Falcon Finalysis provides analytical recommendations and decision support.**

Its company analysis, portfolio results, risk measures, credit indicators and suggested actions
may contain incomplete source data, assumptions or model limitations. They do not constitute an
automatic investment, lending or approval decision.

**A qualified human must review the source documents, apply professional judgement, approve the
decision and confirm the final procedure before any investment, loan or other financial action.**
''')
    st.caption('You can close this notice with the × button. It will appear again in a new browser session.')
    if st.button('I understand — continue', type='primary', width='stretch'):
        st.rerun()


if not st.session_state.get('decision_support_notice_seen'):
    st.session_state.decision_support_notice_seen = True
    decision_support_notice()


def load_demo() -> None:
    st.session_state.frame = demo_company()
    st.session_state.provenance = provenance_for_frame(
        st.session_state.frame, 'Fictional demo', 'Bundled Apex demonstration dataset')
    st.session_state.meta = DEMO_META.copy()
    st.session_state.project_id = None
    st.session_state.project_name = 'Apex • FY2021–FY2025'
    reset_company_outputs()


if st.session_state.pop('open_demo_request', False):
    load_demo()
    st.session_state.open_demo_overview = True


with st.sidebar:
    st.image(str(ACTIVE_LOGO), width=260)
    st.caption('CLEAR FINANCIAL ANALYSIS, STEP BY STEP')
    language = st.selectbox('Interface language', ['English', 'বাংলা'], key='interface_language',
                            help='Navigation and the beginner workflow guide are bilingual. Financial terminology remains visible in English for review consistency.')
    with st.expander('Beginner guide · শুরুর নির্দেশনা', expanded=st.session_state.get('guided_mode', True)):
        st.markdown(workflow_guide(language))
    st.toggle('Guided mode', key='guided_mode', value=True,
              help='Keeps beginner prompts and workflow cues visible.')
    demo_mode = st.toggle('Portfolio Demo Mode', key='demo_mode', help='A guided view of the fictional company. Changes are saved only when you choose Save project.')
    if demo_mode and not st.session_state.get('was_demo_mode', False):
        load_demo()
        st.session_state.open_demo_overview = True
    st.session_state.was_demo_mode = demo_mode
    if st.button('Load Demo Company', width='stretch', type='primary'):
        load_demo()
        st.session_state.open_demo_overview = True
    if 'meta' in st.session_state:
        st.divider()
        st.write(st.session_state.meta['company_name'])
        frame = st.session_state.frame
        st.caption(f'FY{int(frame.Year.min())}–FY{int(frame.Year.max())} · {st.session_state.meta["currency"]}')
        if st.button('Save project', width='stretch'):
            try:
                from components.ui import require_analysis
                analysis = require_analysis()
                project_id = repository().save(st.session_state.meta, frame,
                                               st.session_state.get('project_name', 'Financial analysis'),
                                               st.session_state.get('project_id'), analysis.ratios,
                                               st.session_state.get('provenance'))
                st.session_state.project_id = project_id
                st.session_state.meta['updated_at'] = repository().open(project_id)[0]['updated_at']
                st.success('Project saved. ' + storage_notice())
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                logging.exception('Saving project failed')
                st.error('Could not save. Check that the project folder is writable and the inputs are valid.')
    st.divider()
    st.toggle('Dark workspace', key='dark')
    st.selectbox('BDT display units', ['Automatic', 'Lakh', 'Crore'], key='number_scale',
                 help='Changes how BDT amounts are displayed. Stored values and calculations remain in full units.')
    st.caption(storage_notice())

if st.session_state.get('dark'):
    st.markdown('''<style>
    :root{--ff-ink:#EAF1F8;--ff-muted:#A9B9CA;--ff-line:#2A4058;--ff-surface:#112238;--ff-bg:#091321}
    .stApp,[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:#091321!important;color:#EAF1F8!important}
    [data-testid="stSidebar"]{background:#0E1D30!important;border-color:#263A51!important;color:#EAF1F8!important}
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] a,[data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] label,[data-testid="stSidebar"] span{color:#EAF1F8!important}
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{color:#9FB2C7!important}
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]{background:transparent!important;color:#DCE7F2!important;border:1px solid transparent!important}
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover{background:#18324E!important;border-color:#294865!important}
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"]{background:#12434B!important;color:#F2FFFF!important;border-color:#1A6B73!important;border-left:3px solid #42D4D7!important;font-weight:700!important}
    [data-testid="stMetric"],[data-testid="stVerticalBlockBorderWrapper"],[data-testid="stExpander"]{background:#112238!important;border-color:#2A4058!important;box-shadow:none!important}
    [data-testid="stMetric"] *{color:#EAF1F8!important}
    [data-testid="stMain"] h1,[data-testid="stMain"] h2,[data-testid="stMain"] h3,
    [data-testid="stMain"] [data-testid="stMarkdownContainer"],[data-testid="stWidgetLabel"] p{color:#EAF1F8!important}
    [data-testid="stCaptionContainer"] p{color:#A9B9CA!important}
    [data-testid="stTabs"] button[role="tab"]{color:#B9C9D9!important}
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"]{background:#123B44!important;color:#79E4E6!important}
    [data-baseweb="input"]>div,[data-baseweb="select"]>div,textarea,[data-testid="stDataFrame"]{background:#101F33!important;border-color:#31475F!important;color:#EAF1F8!important}
    .stButton button,.stDownloadButton button,.stLinkButton a,[data-testid="stSidebar"] button{background:#173859!important;color:#F3F8FC!important;border-color:#3B5875!important}
    .stButton button:hover,.stDownloadButton button:hover{background:#205071!important;border-color:#4E7599!important}
    .stButton button p,.stDownloadButton button p,[data-testid="stExpander"] summary{color:#F3F8FC!important}
    [data-baseweb="input"] input,[data-baseweb="select"] input,textarea{color:#EAF1F8!important;background:#101F33!important}
    [data-testid="stSelectbox"] [role="group"],[data-testid="stSelectbox"] [role="combobox"]{background:#101F33!important;color:#EAF1F8!important;border-color:#31475F!important}
    button[aria-label^="Help for"]{background:transparent!important;border-color:transparent!important}
    button[aria-label^="Help for"] svg{stroke:#B9C9D9!important}
    [role="listbox"],[role="option"],[data-baseweb="popover"]{background:#112238!important;color:#EAF1F8!important}
    [role="option"] *{color:#EAF1F8!important}
    [role="option"][aria-selected="true"]{background:#12434B!important}
    [role="dialog"],[role="dialog"] [data-testid="stVerticalBlock"]{background:#112238!important;color:#EAF1F8!important}
    [data-testid="stAlert"]{background:#142B40!important;border:1px solid #36536A!important}
    [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p{color:#EAF1F8!important}
    </style>''', unsafe_allow_html=True)

sections = {
    'Workspace': [st.Page('pages/dashboard.py', title=nav_label('Overview', language), icon=':material/dashboard:', default=True),
                  st.Page('pages/projects.py', title=nav_label('Projects & Data', language), icon=':material/folder_open:'),
                  st.Page('pages/market.py', title=nav_label('Listed Company Data', language), icon=':material/candlestick_chart:'),
                  st.Page('pages/industry_comparison.py', title=nav_label('Industry Comparison', language), icon=':material/compare_arrows:'),
                  st.Page('pages/portfolio.py', title=nav_label('Portfolio Management', language), icon=':material/pie_chart:'),
                  st.Page('pages/data_quality.py', title=nav_label('Data Quality Center', language), icon=':material/rule:'),
                  st.Page('pages/readiness.py', title=nav_label('Data Readiness', language), icon=':material/fact_check:')],
    'Financial Analysis': [st.Page('pages/statements.py', title=nav_label('Financial Statements', language)),
                           st.Page('pages/ratios.py', title=nav_label('Ratio Analysis', language)),
                           st.Page('pages/dupont.py', title=nav_label('DuPont Analysis', language)),
                           st.Page('pages/trends.py', title=nav_label('Trend Analysis', language)),
                           st.Page('pages/working_capital.py', title=nav_label('Working Capital', language)),
                           st.Page('pages/cash_flow.py', title=nav_label('Cash Flow', language)),
                           st.Page('pages/peers.py', title=nav_label('Peer Comparison', language))],
    'Decision Support': [st.Page('pages/risks.py', title=nav_label('Key Insights & Risk Flags', language)),
                         st.Page('pages/scenarios.py', title=nav_label('Scenario Lab', language)),
                         st.Page('pages/health.py', title=nav_label('Health Score Methodology', language)),
                         st.Page('pages/reports.py', title=nav_label('Generated Report', language)),
                         st.Page('pages/valuation.py', title=nav_label('Valuation Lab', language), icon=':material/monitoring:'),
                         st.Page('pages/credgrid.py', title=nav_label('CredGrid AI', language), icon=':material/credit_score:')],
    'Falcon Finalysis': [st.Page('pages/governance.py', title=nav_label('Local Governance', language), icon=':material/admin_panel_settings:'),
                        st.Page('pages/about.py', title=nav_label('About Falcon Finalysis', language))],
}
nav = st.navigation(sections, position='hidden')
with st.sidebar:
    for group, pages in sections.items():
        st.caption(group.upper())
        for page in pages:
            if demo_mode and any(name in page.title for name in ['Projects & Data', 'Peer Comparison']):
                continue
            st.page_link(page)
if st.session_state.pop('open_demo_overview', False):
    st.switch_page('pages/dashboard.py')
try:
    nav.run()
except Exception:
    logging.exception('Page failed')
    st.error('This view could not be completed. Check the data and try again. Technical details are saved locally in falcon_finalysis.log.')
