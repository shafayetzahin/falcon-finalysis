"""Interactive scenario assumptions, comparisons and sensitivity tornado."""
import json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.scenario_engine import Scenario, baseline, model, sensitivity, ASSUMPTIONS
from components.ui import require_analysis, company_header, repository
from components.formatting import fmt, unit_for

a = require_analysis()
company_header('Scenario Lab')
st.caption('A one-year operating scenario. Change assumptions to see earnings and funding implications.')
try:
    base = baseline(a.statements.iloc[-1])
except ValueError as exc:
    st.info(str(exc))
    st.stop()
with st.expander('Model assumptions', expanded=False):
    st.write(ASSUMPTIONS)
project = st.session_state.get('project_id')
if project:
    saved = repository().scenarios(project)
    if saved:
        selected = st.selectbox('Saved scenario', [r['id'] for r in saved], format_func=lambda i: next(r['name'] for r in saved if r['id'] == i))
        if st.button('Load saved scenario'):
            st.session_state.scenario = json.loads(next(r['assumptions'] for r in saved if r['id'] == selected))
            for key in list(st.session_state):
                if key.startswith('driver_'):
                    del st.session_state[key]
            st.rerun()
active = Scenario(**st.session_state.get('scenario', base.to_dict()))
left, right = st.columns([1, 2])
with left, st.container(border=True):
    st.subheader('Operating assumptions')
    values = {}
    labels = {'revenue_growth': 'Revenue Growth %', 'cogs_ratio': 'COGS / Revenue %',
              'opex_ratio': 'Operating Expenses / Revenue %', 'interest_rate': 'Interest Rate %',
              'tax_rate': 'Tax Rate %', 'receivable_days': 'Receivable Days', 'inventory_days': 'Inventory Days',
              'payable_days': 'Payable Days', 'capex': 'Capital Expenditure', 'debt': 'Debt'}
    for key, label in labels.items():
        percent = key in ['revenue_growth', 'cogs_ratio', 'opex_ratio', 'interest_rate', 'tax_rate']
        factor = 100 if percent else 1
        minimum = -99. if key == 'revenue_growth' else 0.
        maximum = 500. if key == 'revenue_growth' else 200. if key in ['cogs_ratio', 'opex_ratio'] else 100. if percent else None
        values[key] = st.number_input(label, min_value=minimum, max_value=maximum,
                                      value=float(getattr(active, key)*factor), step=1. if percent or 'days' in key else 1_000_000.,
                                      key='driver_'+key)/factor
    case = Scenario(**values)
    st.session_state.scenario = case.to_dict()
    if st.button('Reset to base case'):
        st.session_state.scenario = base.to_dict()
        for key in list(st.session_state):
            if key.startswith('driver_'):
                del st.session_state[key]
        st.rerun()
with right:
    try:
        base_result = model(a.statements.iloc[-1], base)
        case_result = model(a.statements.iloc[-1], case)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    st.subheader('Base case vs scenario')
    compare = pd.DataFrame({'Base case': base_result, 'Scenario': case_result, 'Change': case_result-base_result})
    formatted = compare.astype(object)
    for metric in compare.index:
        for col in compare:
            formatted.loc[metric, col] = fmt(compare.loc[metric, col], unit_for(metric), st.session_state.meta['currency'])
    st.dataframe(formatted, width='stretch', height=610)
    st.caption('ROA / ROE and cash flows are model proxies. Both columns are projected cases; the base case is not historical reported cash flow.')
    scenario_name = st.text_input('Scenario name', 'Operating scenario')
    if st.button('Save scenario', disabled=not project):
        if scenario_name.strip():
            repository().save_scenario(project, scenario_name, case.to_dict())
            st.success('Scenario assumptions saved to this project.')
        else:
            st.error('Enter a scenario name.')
    if not project:
        st.caption('Save the company project first to store scenarios.')
st.subheader('Sensitivity analysis')
output = st.selectbox('Output metric', ['Net Income', 'EBIT', 'EBITDA', 'ROE', 'Free Cash Flow'])
sens = sensitivity(a.statements.iloc[-1], case, output)
st.caption('One driver changes at a time. Revenue growth and gross margin: ±5pp; operating expense ratio: ±3pp; interest: ±2pp; receivable and inventory days: ±10 days. Assumptions are clipped to valid bounds. FCF is a proxy.')
st.dataframe(sens.style.format({c: '{:,.3f}' for c in sens.columns if c != 'Driver'}, na_rep='N/A'), hide_index=True, width='stretch')
fig = go.Figure()
for label, color in [('Minus shock', '#173859'), ('Plus shock', '#008C95')]:
    fig.add_trace(go.Bar(y=sens.Driver, x=sens[label]-sens.Base, name=label, orientation='h', marker_color=color))
fig.update_layout(title=f'Impact on {output} vs active scenario', barmode='relative', height=360,
                  template='plotly_dark' if st.session_state.get('dark') else 'plotly_white',
                  xaxis_title='Change in decimal return' if output == 'ROE' else st.session_state.meta['currency'],
                  margin=dict(l=10, r=10, t=55, b=20), legend=dict(orientation='h'))
st.plotly_chart(fig, width='stretch')
