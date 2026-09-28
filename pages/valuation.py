"""Public-company DCF, WACC, ROIC and trading-comps workspace."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.ui import header
from core.valuation_engine import (calculate_wacc, comparable_valuation,
                                   discounted_cash_flow, roic_reinvestment)


header("Valuation Lab", "Build a reviewable screening valuation from verified company statements and explicit market assumptions.")
st.warning("Valuation decision support only. Verify filings, market data, peer definitions and every assumption. A qualified human must approve any investment or transaction conclusion.")

if "frame" not in st.session_state:
    st.info("Select a listed company or load a project before building a valuation.")
    st.page_link("pages/market.py", label="Choose a DSE/CSE company →")
    st.stop()

frame = st.session_state.frame.copy().sort_values("Year")
meta = st.session_state.get("meta", {})
latest = frame.iloc[-1]


def value(name: str, default: float = 0.0) -> float:
    result = pd.to_numeric(latest.get(name), errors="coerce")
    return float(result) if pd.notna(result) else float(default)

st.subheader(f"{meta.get('company_name', 'Selected company')} · FY{int(latest['Year'])}")
st.caption("Blue inputs are reviewer assumptions. Statement-derived defaults remain editable because exchange summaries may be incomplete.")

with st.expander("1 · Capital, market and discount-rate assumptions", expanded=True):
    capital_cols = st.columns(4)
    shares = capital_cols[0].number_input("Shares outstanding", min_value=.01,
                                         value=max(value("Shares Outstanding", 1), .01))
    market_price = capital_cols[1].number_input("Current market price per share", min_value=0.0,
                                                value=max(value("Market Price Per Share"), 0.0))
    debt = capital_cols[2].number_input("Interest-bearing debt", min_value=0.0,
                                       value=max(value("Short-Term Debt") + value("Long-Term Debt"), 0.0))
    cash = capital_cols[3].number_input("Cash and equivalents", min_value=0.0,
                                       value=max(value("Cash"), 0.0))
    rate_cols = st.columns(5)
    risk_free = rate_cols[0].number_input("Risk-free rate %", 0.0, 100.0, 10.0, .25) / 100
    equity_premium = rate_cols[1].number_input("Equity risk premium %", 0.0, 100.0, 6.0, .25) / 100
    beta = rate_cols[2].number_input("Reviewed beta", 0.0, 10.0, 1.0, .05)
    debt_cost = rate_cols[3].number_input("Pre-tax cost of debt %", 0.0, 100.0, 12.0, .25) / 100
    tax_rate = rate_cols[4].number_input("Marginal tax rate %", 0.0, 99.0, 25.0, .5) / 100
    rate_source = st.text_input("Market assumptions source and as-of date",
                                placeholder="Example: Bangladesh government security, reviewed market source, YYYY-MM-DD")

market_cap = shares * market_price
try:
    wacc = calculate_wacc(market_cap, debt, risk_free, equity_premium, beta, debt_cost, tax_rate)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

wacc_cols = st.columns(5)
wacc_cols[0].metric("Market capitalization", f"{market_cap:,.1f}")
wacc_cols[1].metric("Cost of equity", f"{wacc.cost_of_equity:.2%}")
wacc_cols[2].metric("After-tax debt cost", f"{wacc.after_tax_cost_of_debt:.2%}")
wacc_cols[3].metric("Equity weight", f"{wacc.equity_weight:.2%}")
wacc_cols[4].metric("WACC", f"{wacc.wacc:.2%}")

st.subheader("2 · ROIC, reinvestment and intrinsic growth")
roic = roic_reinvestment(frame, tax_rate)
st.dataframe(roic.style.format({"NOPAT": "{:,.1f}", "Invested Capital": "{:,.1f}",
                                "ROIC": "{:.2%}", "Reinvestment": "{:,.1f}",
                                "Reinvestment Rate": "{:.2%}", "Intrinsic Growth": "{:.2%}"}),
             hide_index=True, width="stretch")
st.caption("Screening definitions: invested capital = interest-bearing debt + equity - cash; reinvestment = capex - depreciation + change in current working capital.")

st.subheader("3 · FCFF discounted cash flow")
base_default = max(value("Operating Cash Flow") - value("Capital Expenditure"), 0.0)
dcf_cols = st.columns(3)
base_fcff = dcf_cols[0].number_input("Reviewed base FCFF", min_value=0.0, value=base_default)
forecast_growth = dcf_cols[1].number_input("Annual FCFF growth %", -99.0, 200.0, 8.0, .5) / 100
terminal_growth = dcf_cols[2].number_input("Terminal growth %", 0.0, 50.0, 5.0, .25) / 100
years = st.slider("Explicit forecast years", 3, 10, 5)

st.subheader("4 · Trading comparable inputs")
peers = st.data_editor(pd.DataFrame([
    {"Company": "Peer 1", "EV/Revenue": None, "EV/EBITDA": None, "P/E": None},
    {"Company": "Peer 2", "EV/Revenue": None, "EV/EBITDA": None, "P/E": None},
    {"Company": "Peer 3", "EV/Revenue": None, "EV/EBITDA": None, "P/E": None},
]), num_rows="dynamic", hide_index=True, width="stretch", key="valuation_peers")
st.caption("Use comparable companies with aligned currency, fiscal basis and multiple definitions. Empty or nonpositive multiples are excluded.")

if st.button("Calculate valuation range", type="primary"):
    if not rate_source.strip():
        st.error("Enter the market-assumption source and as-of date.")
    else:
        try:
            dcf = discounted_cash_flow(base_fcff, [forecast_growth] * years, wacc.wacc,
                                       terminal_growth, cash, debt, shares)
            comps = comparable_valuation(peers, value("Revenue"), value("EBITDA"),
                                         value("Net Income"), debt, cash, shares)
            st.session_state.valuation_result = (dcf, comps, rate_source)
        except ValueError as exc:
            st.error(str(exc))

result = st.session_state.get("valuation_result")
if result:
    dcf, comps, saved_source = result
    st.divider()
    st.subheader("Valuation result")
    result_cols = st.columns(4)
    result_cols[0].metric("DCF enterprise value", f"{dcf.enterprise_value:,.1f}")
    result_cols[1].metric("DCF equity value", f"{dcf.equity_value:,.1f}")
    result_cols[2].metric("DCF value per share", f"{dcf.value_per_share:,.2f}")
    result_cols[3].metric("Terminal value share", f"{dcf.terminal_value_share:.1%}")
    st.dataframe(dcf.forecast.style.format({"Growth": "{:.2%}", "FCFF": "{:,.1f}",
                                            "Discount Factor": "{:.4f}", "PV of FCFF": "{:,.1f}"}),
                 hide_index=True, width="stretch")
    st.markdown("**DCF value-per-share sensitivity**")
    display_sensitivity = dcf.sensitivity.copy()
    display_sensitivity.index = [f"{item:.2%}" for item in display_sensitivity.index]
    display_sensitivity.columns = [f"{item:.2%}" for item in display_sensitivity.columns]
    st.dataframe(display_sensitivity.style.format("{:,.2f}"), width="stretch")

    if not comps.empty:
        st.markdown("**Comparable-company implied values**")
        st.dataframe(comps.style.format({"Selected multiple": "{:.2f}x",
                                         "Implied equity value": "{:,.1f}",
                                         "Implied value per share": "{:,.2f}"}),
                     hide_index=True, width="stretch")
        ranges = comps.groupby("Method")["Implied value per share"].agg(["min", "max"]).reset_index()
    else:
        st.info("Enter reviewed peer multiples to add comparable-company valuation ranges.")
        ranges = pd.DataFrame(columns=["Method", "min", "max"])
    ranges = pd.concat([ranges, pd.DataFrame([{"Method": "DCF base",
                                               "min": dcf.value_per_share,
                                               "max": dcf.value_per_share}])], ignore_index=True)
    st.markdown("**Football-field valuation summary**")
    fig = go.Figure()
    for _, row in ranges.iterrows():
        fig.add_trace(go.Scatter(x=[row["min"], row["max"]], y=[row["Method"], row["Method"]],
                                 mode="lines+markers", line={"width": 12}, name=row["Method"]))
    if market_price > 0:
        fig.add_vline(x=market_price, line_dash="dash", annotation_text="Current price")
    fig.update_layout(height=360, showlegend=False, xaxis_title="Implied value per share",
                      template="plotly_dark" if st.session_state.get("dark") else "plotly_white")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.caption(f"Assumption source: {saved_source}. This is a screening valuation, not a fairness opinion or investment recommendation.")
