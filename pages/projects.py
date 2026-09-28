"""Create, map, validate, manually edit and reopen local company projects."""
from datetime import date
import streamlit as st
import pandas as pd
from components.ui import repository, header
from core.config import FIELDS, CURRENCIES
from core.validation import validate
from data.parsers import read_file, suggest_mapping, prepare
from data.document_import import extract_pdfs, extract_workbook, apply_scale
from data.database import stamp
from data.provenance import (PROVENANCE_COLUMNS, provenance_for_frame,
                             provenance_from_evidence, merge_provenance, changed_provenance)

header('Projects & Data', 'Create a company, import values, review data quality and save your analysis locally.')
repo = repository()
st.subheader('Choose the easiest starting point')
start_cols = st.columns(4)
with start_cols[0]:
    with st.container(border=True):
        st.markdown('**Listed company ticker**')
        st.caption('DSE/CSE details and dated market prices.')
        st.page_link('pages/market.py', label='Open ticker lookup')
with start_cols[1]:
    with st.container(border=True):
        st.markdown('**Annual report PDF**')
        st.caption('Extract candidate statement rows, then review them.')
with start_cols[2]:
    with st.container(border=True):
        st.markdown('**Excel or CSV**')
        st.caption('Map columns or read a statement-style workbook.')
with start_cols[3]:
    with st.container(border=True):
        st.markdown('**Manual entry**')
        st.caption('Enter 3–10 fiscal years directly.')
tabs = st.tabs(['Company setup', 'Upload & map', 'Manual editor', 'Saved projects'])
with tabs[0]:
    old = st.session_state.get('meta', {})
    with st.form('company_setup'):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input('Company name', old.get('company_name', ''), max_chars=150)
            industry = st.text_input('Industry', old.get('industry', ''), max_chars=100)
            country = st.text_input('Country', old.get('country', ''), max_chars=100)
        with c2:
            current_currency = old.get('currency', 'BDT')
            choices = list(CURRENCIES) + ['Custom']
            currency = st.selectbox('Reporting currency', choices, index=choices.index(current_currency) if current_currency in choices else 5)
            custom = st.text_input('Custom currency text', current_currency if current_currency not in CURRENCIES else '', max_chars=20)
            project_name = st.text_input('Project name', st.session_state.get('project_name', 'Financial analysis'), max_chars=150)
        description = st.text_area('Description', old.get('description', ''), max_chars=2000)
        start = st.number_input('First fiscal year for a new blank project', 1900, 2198, date.today().year-4)
        count = st.slider('Number of years for a new blank project', 3, 10, 5)
        existing = 'frame' in st.session_state
        action = st.radio('Apply setup to', ['Current project', 'New blank project'] if existing else ['New blank project'])
        submitted = st.form_submit_button('Apply company setup', type='primary')
    if submitted:
        if not name.strip() or not project_name.strip() or currency == 'Custom' and not custom.strip():
            st.error('Enter company, project and currency names.')
        elif start + count - 1 > 2200:
            st.error('The final year must be at most 2200.')
        else:
            st.session_state.meta = dict(company_name=name.strip(), industry=industry, country=country,
                                         currency=custom.strip() if currency == 'Custom' else currency,
                                         description=description, updated_at=stamp())
            st.session_state.project_name = project_name
            if action == 'New blank project':
                st.session_state.frame = pd.DataFrame({'Year': range(int(start), int(start)+count)}).reindex(columns=['Year']+FIELDS)
                st.session_state.provenance = pd.DataFrame(columns=PROVENANCE_COLUMNS)
                st.session_state.project_id = None
                st.session_state.pop('scenario', None)
            st.success('Setup applied. Enter or upload financial figures, then Save project.')
            st.rerun()
with tabs[1]:
    st.caption('One row per fiscal year. First row: column labels. Full currency units. Positive expense/capex/dividend magnitudes; signed cash flows. Only values-only XLSX or UTF-8 CSV; no macros or formulas are executed.')
    from reports.excel_report import input_template
    st.download_button('Download blank Excel template with field guide', input_template(),
                       'Falcon_Finalysis_template.xlsx')
    file = st.file_uploader('Financial statements', type=['xlsx', 'csv'])
    sheet = st.text_input('Excel worksheet name (blank uses the active worksheet)')
    if file:
        try:
            raw = read_file(file.getvalue(), file.name, sheet or None)
            st.dataframe(raw.head(10), width='stretch')
            defaults = suggest_mapping(list(raw.columns))
            saved_mappings = repo.list_import_mappings()
            if saved_mappings:
                chosen_mapping = st.selectbox(
                    'Reuse a saved column mapping (optional)', [None] + [item['id'] for item in saved_mappings],
                    format_func=lambda value: 'Use automatic suggestions' if value is None else next(
                        item['name'] for item in saved_mappings if item['id'] == value))
                if chosen_mapping is not None:
                    reused = repo.open_import_mapping(chosen_mapping)
                    defaults = {column: reused.get(column, defaults[column]) for column in raw.columns}
            st.caption('Review mappings. Ignore unused columns; choose a field for unrecognized labels.')
            mapping = {}
            with st.expander('Column mapping', expanded=any(v == 'Ignore' for v in defaults.values())):
                cols = st.columns(3)
                options = ['Ignore', 'Year'] + FIELDS
                for i, (source, target) in enumerate(defaults.items()):
                    with cols[i % 3]:
                        target = target if target in options else 'Ignore'
                        mapping[source] = st.selectbox(source, options, index=options.index(target), key=f'map_{file.name}_{source}')
            mapping_name = st.text_input('Save this mapping as (optional)',
                                         placeholder='Example: Bank annual export')
            if st.button('Save column mapping', disabled=not mapping_name.strip()):
                repo.save_import_mapping(mapping_name, mapping)
                st.success('Reusable column mapping saved on this device.')
            if st.button('Import mapped data', type='primary'):
                if 'meta' not in st.session_state:
                    st.error('Create company setup first so the reporting currency is explicit.')
                else:
                    st.session_state.frame = prepare(raw, mapping)
                    source_type = 'CSV upload' if file.name.lower().endswith('.csv') else 'Excel upload'
                    reference = file.name + (f' · sheet {sheet}' if sheet else '')
                    st.session_state.provenance = merge_provenance(
                        st.session_state.get('provenance'),
                        provenance_for_frame(st.session_state.frame, source_type, reference))
                    st.session_state.meta['updated_at'] = stamp()
                    st.session_state.pop('scenario', None)
                    st.success('Imported. Review validation below and Save project to retain your changes.')
        except ValueError as exc:
            st.error(str(exc))

    st.divider()
    st.subheader('Annual report PDF or statement-style Excel')
    st.write('Use this for tables with financial line items down the left and years across the top. Falcon Finalysis extracts candidates only; review every value before importing.')
    pdf_files = st.file_uploader('Annual report PDFs (upload more than one when needed to reach 3 years)',
                                 type=['pdf'], accept_multiple_files=True, key='annual_reports')
    layout_file = st.file_uploader('Or a statement-style Excel workbook', type=['xlsx'], key='statement_layout')
    if st.button('Extract statement candidates', disabled=not pdf_files and not layout_file):
        try:
            if pdf_files:
                result = extract_pdfs([(item.getvalue(), item.name) for item in pdf_files])
            else:
                result = extract_workbook(layout_file.getvalue(), layout_file.name)
            st.session_state.statement_extraction = result
        except ValueError as exc:
            st.error(str(exc))
    extraction = st.session_state.get('statement_extraction')
    if extraction is not None:
        extracted_values = int(extraction.frame[FIELDS].notna().sum().sum())
        evidence_sources = extraction.evidence['Source'].nunique() if not extraction.evidence.empty else 0
        summary_cols = st.columns(3)
        summary_cols[0].metric('Fiscal years found', extraction.frame.Year.nunique())
        summary_cols[1].metric('Values extracted', extracted_values)
        summary_cols[2].metric('Source locations', evidence_sources)
        review_tab, evidence_tab, import_tab = st.tabs(['1 · Review values', '2 · Check source evidence', '3 · Import'])
        with review_tab:
            st.caption(f'Detected unit: {extraction.unit_hint}. Edit incorrect candidates or clear uncertain cells before importing.')
            candidate = st.data_editor(extraction.frame, hide_index=True, width='stretch', key='extraction_editor')
            for note in extraction.notes:
                st.caption(note)
        with evidence_tab:
            st.write('Match each extracted value to its original label, file, page, table or worksheet.')
            st.dataframe(extraction.evidence, hide_index=True, width='stretch')
        with import_tab:
            scale_name = st.selectbox('Amounts in the source are', ['Full units', 'Thousands', 'Millions'],
                                      index={'Unknown': 0, 'Thousands': 1, 'Millions': 2}.get(extraction.unit_hint, 0))
            multiplier = {'Full units': 1, 'Thousands': 1_000, 'Millions': 1_000_000}[scale_name]
            merge = st.checkbox('Merge with years already in the current project', value='frame' in st.session_state)
            reviewed_ok = st.checkbox('I reviewed the extracted values and source evidence')
            import_reviewed = st.button('Import reviewed statement values', type='primary', disabled=not reviewed_ok)
        if import_reviewed:
            if 'meta' not in st.session_state:
                st.error('Create company setup first so the reporting currency is explicit.')
            else:
                try:
                    reviewed = apply_scale(candidate, multiplier)
                    if merge and 'frame' in st.session_state:
                        current = st.session_state.frame.set_index('Year')
                        incoming = reviewed.set_index('Year')
                        combined = incoming.combine_first(current).reset_index()
                    else:
                        combined = reviewed
                    st.session_state.frame = prepare(combined)
                    st.session_state.provenance = merge_provenance(
                        st.session_state.get('provenance'),
                        provenance_from_evidence(extraction.evidence, accepted_frame=reviewed))
                    st.session_state.meta['updated_at'] = stamp()
                    st.session_state.pop('scenario', None)
                    st.session_state.import_report = {
                        'Years imported': int(reviewed.Year.nunique()),
                        'Values imported': int(reviewed[FIELDS].notna().sum().sum()),
                        'Source locations': int(evidence_sources),
                        'Applied scale': scale_name,
                    }
                    st.success('Reviewed values imported. Check reconciliation messages below, then Save project.')
                except ValueError as exc:
                    st.error(str(exc))
    if st.session_state.get('import_report'):
        with st.expander('Last import report', expanded=True):
            st.json(st.session_state.import_report)
with tabs[2]:
    if 'frame' in st.session_state:
        st.caption('Edit full currency values. Scroll horizontally for all fields. Add or remove rows to retain 3–10 consecutive years. Blank means unavailable.')
        with st.form('editor_form'):
            edited = st.data_editor(st.session_state.frame, num_rows='dynamic', hide_index=True, width='stretch',
                                    column_config={'Year': st.column_config.NumberColumn(format='%d', required=True)}, key='statement_editor')
            apply = st.form_submit_button('Validate & apply edits', type='primary')
        if apply:
            try:
                before = st.session_state.frame.copy()
                st.session_state.frame = prepare(edited)
                st.session_state.provenance = merge_provenance(
                    st.session_state.get('provenance'), changed_provenance(before, st.session_state.frame))
                st.session_state.meta['updated_at'] = stamp()
                st.session_state.pop('scenario', None)
                st.success('Edits applied. Save project to keep them after restart.')
            except ValueError as exc:
                st.error(str(exc))
    else:
        st.info('Create a company setup or load the demo before entering figures.')
with tabs[3]:
    projects = repo.list_projects()
    if projects:
        chosen = st.selectbox('Saved project', [p['id'] for p in projects], format_func=lambda i: next(p['name'] + ' — ' + p['company_name'] for p in projects if p['id'] == i))
        cols = st.columns(3)
        if cols[0].button('Open selected project'):
            meta, frame = repo.open(chosen)
            st.session_state.meta, st.session_state.frame = meta, frame
            st.session_state.provenance = repo.provenance(chosen)
            st.session_state.project_id, st.session_state.project_name = chosen, meta['name']
            st.session_state.pop('scenario', None)
            st.rerun()
        if cols[1].button('Duplicate selected project'):
            repo.duplicate(chosen)
            st.rerun()
        rename = st.text_input('New name for selected project')
        if st.button('Rename selected project'):
            if rename.strip():
                repo.rename(chosen, rename)
                if st.session_state.get('project_id') == chosen:
                    st.session_state.project_name = rename
                st.rerun()
            else:
                st.error('Enter a new name.')
        confirm = st.checkbox('Delete this saved project and its stored scenarios permanently')
        if st.button('Delete selected project', disabled=not confirm):
            repo.delete(chosen)
            if st.session_state.get('project_id') == chosen:
                st.session_state.project_id = None
            st.rerun()
    else:
        st.info('No saved projects yet. Use Save project in the sidebar after importing or entering data.')

if 'frame' in st.session_state:
    st.divider()
    st.subheader('Data quality review')
    st.session_state.tolerance = st.number_input('Reconciliation tolerance (%)', 0., 10., st.session_state.get('tolerance', .01)*100, step=.1)/100
    issues = validate(st.session_state.frame, st.session_state.tolerance)
    if not issues:
        st.success('All available accounting reconciliations passed. This is a consistency check, not an audit.')
    for issue in issues:
        text = f'{issue.year} {issue.message}'
        if issue.severity == 'ERROR':
            st.error(text)
        elif issue.severity == 'WARNING':
            st.warning('DATA QUALITY WARNING · ' + text)
        else:
            st.info(text)
    provenance = st.session_state.get('provenance')
    if isinstance(provenance, pd.DataFrame) and not provenance.empty:
        with st.expander(f'Value sources ({len(provenance):,} recorded values)'):
            st.dataframe(provenance, hide_index=True, width='stretch')
