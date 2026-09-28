"""Data completeness, analysis availability and source coverage."""
import pandas as pd
import streamlit as st

from components.ui import header
from core.readiness import readiness, field_coverage


header('Data Readiness', 'See what the current dataset can support and what to collect next.')

if 'frame' not in st.session_state:
    st.info('Load a company, import statements or use the demo to review data readiness.')
    st.page_link('pages/projects.py', label='Open Projects & Data')
    st.stop()

frame = st.session_state.frame
areas = readiness(frame)
fields = field_coverage(frame)
provenance = st.session_state.get('provenance')

overall = float(frame.drop(columns=['Year'], errors='ignore').notna().sum().sum())
possible = max(1, len(frame) * max(1, len(frame.columns) - 1))
ready_count = int(areas.Status.eq('Ready').sum())
source_count = len(provenance) if isinstance(provenance, pd.DataFrame) else 0

cols = st.columns(3)
cols[0].metric('Financial-data completion', f'{overall / possible:.0%}')
cols[1].metric('Analysis areas ready', f'{ready_count} of {len(areas)}')
cols[2].metric('Values with recorded sources', f'{source_count:,}')

st.subheader('What can be analysed now')
st.caption('Ready means the latest year contains every field required by that analysis. Coverage measures all selected years.')
shown = areas.copy()
shown['Coverage'] = shown['Coverage'].map(lambda value: f'{value:.0%}')
st.dataframe(shown, hide_index=True, width='stretch',
             column_config={'Status': st.column_config.TextColumn(width='small'),
                            'Missing latest-year fields': st.column_config.TextColumn(width='large')})

missing = areas.loc[areas.Status.ne('Ready'), ['Analysis area', 'Missing latest-year fields']]
if missing.empty:
    st.success('All defined analysis areas have the required latest-year inputs.')
else:
    st.subheader('Recommended next data')
    for row in missing.itertuples(index=False):
        st.write(f'**{row[0]}:** {row[1]}')

with st.expander('Field-by-field completion'):
    display = fields.copy()
    display['Coverage'] = display['Coverage'].map(lambda value: f'{value:.0%}')
    st.dataframe(display, hide_index=True, width='stretch')

with st.expander('Value sources and provenance'):
    if isinstance(provenance, pd.DataFrame) and not provenance.empty:
        st.dataframe(provenance, hide_index=True, width='stretch')
    else:
        st.info('No cell-level sources are recorded yet. New exchange, PDF, Excel, CSV and manual imports will record them here.')

st.page_link('pages/projects.py', label='Add or correct financial data →')
