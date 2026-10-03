"""CredGrid AI transparent small-business credit decision support."""
from datetime import date
from html import escape
import json

import numpy as np
import pandas as pd
import streamlit as st

from components.ui import header, repository
from core.credit_engine import CREDIT_MODEL_VERSION, TRANSACTION_COLUMNS, analyze_credit
from data.credit_data import evidence_checks, read_transaction_file, suggest_transaction_categories


DOCUMENTS = ["Business bank/MFS statement", "Personal bank/MFS statement",
             "Trade licence or registration", "Marketplace/sales statement",
             "Tax or other official document"]


def records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def demo_transactions() -> pd.DataFrame:
    rows, balance = [], 90_000.0
    start = pd.Timestamp.today().normalize().to_period("M").start_time - pd.DateOffset(months=7)
    for month in range(8):
        base = start + pd.DateOffset(months=month)
        inflow = 120_000 + 4_000 * month + 7_000 * np.sin(month)
        for day, description, amount, category in [
            (2, "Online and shop sales", inflow, "Business revenue"),
            (7, "Inventory suppliers", -(56_000 + 1_500 * month), "Operating expense"),
            (12, "Shop rent", -20_000, "Operating expense"),
            (20, "Utilities and delivery", -(8_000 + 300 * month), "Operating expense"),
        ]:
            balance += amount
            rows.append({"Date": base + pd.Timedelta(days=day), "Description": description,
                         "Amount": amount, "Balance": balance, "Category": category,
                         "Source": "Fictional CredGrid demonstration statement"})
    return pd.DataFrame(rows, columns=TRANSACTION_COLUMNS)


def load_demo() -> None:
    st.session_state.cg_transactions = demo_transactions()
    st.session_state.cg_business_name = "Falcon Corner Shop (fictional)"
    st.session_state.cg_business_type = "Retail / online shop"
    st.session_state.cg_purpose = "Inventory purchase"
    st.session_state.cg_requested = 250_000.0
    st.session_state.cg_tenure = 12
    st.session_state.cg_existing_debt = 5_000.0
    st.session_state.cg_dscr = 1.30
    st.session_state.cg_risk_free = 10.0
    st.session_state.cg_operating_premium = 3.0
    st.session_state.cg_liquidity_premium = 2.0
    st.session_state.cg_credit_premium = 4.0
    st.session_state.cg_reviewed_expenses = 0.0
    st.session_state.cg_rate_source = "Fictional demonstration benchmark — replace with reviewed source"
    st.session_state.cg_rate_date = date.today()
    st.session_state.cg_documents = DOCUMENTS[:4]
    st.session_state.cg_consent = True
    st.session_state.cg_case_id = None
    st.session_state.pop("cg_analysis", None)


def restore_case(meta: dict, payload: dict) -> None:
    for key, value in payload.get("inputs", {}).items():
        if key == "cg_rate_date" and isinstance(value, str):
            value = date.fromisoformat(value)
        st.session_state[key] = value
    frame = pd.DataFrame(payload.get("transactions", [])).reindex(columns=TRANSACTION_COLUMNS)
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    st.session_state.cg_transactions = frame
    st.session_state.cg_case_id = meta["id"]
    st.session_state.pop("cg_analysis", None)


def case_payload(inputs: dict, transactions: pd.DataFrame, analysis=None) -> dict:
    output = {"inputs": inputs, "transactions": records(transactions)}
    if analysis is not None:
        output["analysis"] = {
            "score": analysis.score, "band": analysis.band, "confidence": analysis.confidence,
            "reasons": analysis.reasons, "profile": analysis.profile, "proposal": analysis.proposal,
            "components": records(analysis.components),
        }
    return output


def report_html(business_name: str, analysis, benchmark_source: str,
                benchmark_date: date) -> bytes:
    score = "Withheld" if analysis.score is None else f"{analysis.score:.1f} / 100"
    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in analysis.reasons)
    proposal = "".join(
        f"<tr><th>{escape(key)}</th><td>{value:,.4f}</td></tr>"
        if isinstance(value, (int, float)) else
        f"<tr><th>{escape(key)}</th><td>{escape(str(value))}</td></tr>"
        for key, value in analysis.proposal.items())
    html = f'''<!doctype html><html><head><meta charset="utf-8"><title>CredGrid review</title>
<style>body{{font:15px Arial;max-width:1000px;margin:40px auto;color:#17324d}}h1,h2{{color:#073b4c}}
table{{border-collapse:collapse;width:100%;margin:15px 0}}th,td{{border:1px solid #ccd7df;padding:8px;text-align:left}}
th{{background:#e9f5f4}}.notice{{background:#fff3cd;padding:14px;border-left:5px solid #c68a00}}</style></head><body>
<h1>CredGrid AI — {escape(business_name)}</h1>
<div class="notice"><strong>Human decision required.</strong> This unvalidated scorecard is decision support. A qualified reviewer must verify evidence, apply policy and confirm the final decision.</div>
<h2>Cash-flow profile</h2><p><strong>{score}</strong> · {escape(analysis.band)} · confidence {analysis.confidence:.0%}</p>
{analysis.components.to_html(index=False, border=0, float_format=lambda value: f'{value:,.4f}')}
<h2>Reason codes</h2><ul>{reasons}</ul><h2>Modeled proposal</h2><table>{proposal}</table>
<p>Benchmark source: {escape(benchmark_source)} · as of {benchmark_date:%d/%m/%Y}</p>
<p>The proposal is not approval, a credit bureau score, or a probability of default. It excludes legal and regulatory eligibility checks.</p>
</body></html>'''
    return html.encode("utf-8")


header("CredGrid AI", "Explainable cash-flow credit analysis for small businesses and online shops.")
st.warning("Decision support only. CredGrid AI cannot approve or decline a loan. A trained human must verify every source, apply the lender's policy, document the rationale and confirm the final procedure.")

with st.expander("What CredGrid does — and does not do", expanded=True):
    st.write("It summarizes reviewed transaction history, scores six disclosed cash-flow factors and models repayment capacity. It never infers missing identity, income or repayment history.")
    st.caption("This first scorecard is not calibrated to defaults and must not be used in production until legal, privacy, fair-lending and outcome-validation work is complete.")

demo_col, saved_col = st.columns(2)
if demo_col.button("Load fictional CredGrid case", type="primary", width="stretch"):
    load_demo()
    st.rerun()

with saved_col.popover("Open a saved credit case", width="stretch"):
    cases = repository().list_credit_cases()
    if cases:
        chosen_case = st.selectbox("Saved case", [case["id"] for case in cases],
                                   format_func=lambda value: next(case["business_name"] for case in cases
                                                                  if case["id"] == value))
        if st.button("Open selected case", width="stretch"):
            meta, payload = repository().open_credit_case(chosen_case)
            restore_case(meta, payload)
            st.rerun()
    else:
        st.info("No saved credit cases yet.")

for key, value in {
    "cg_requested": 100_000.0, "cg_tenure": 12, "cg_existing_debt": 0.0,
    "cg_dscr": 1.30, "cg_risk_free": 0.0, "cg_operating_premium": 3.0,
    "cg_liquidity_premium": 2.0, "cg_credit_premium": 4.0,
    "cg_reviewed_expenses": 0.0,
}.items():
    st.session_state.setdefault(key, value)

st.subheader("1 · Borrower consent and request")
identity_cols = st.columns(2)
business_name = identity_cols[0].text_input("Business name", key="cg_business_name")
business_type = identity_cols[1].text_input("Business type", key="cg_business_type")
purpose = st.text_input("Loan purpose", key="cg_purpose")
request_cols = st.columns(4)
requested = request_cols[0].number_input("Requested amount (BDT)", min_value=1.0, step=10_000.0,
                                         key="cg_requested")
tenure = request_cols[1].number_input("Requested tenure (months)", min_value=1, max_value=60,
                                     step=1, key="cg_tenure")
existing_debt = request_cols[2].number_input("Existing monthly debt service (BDT)", min_value=0.0,
                                             step=1_000.0, key="cg_existing_debt")
minimum_dscr = request_cols[3].number_input("Minimum DSCR", min_value=1.0, max_value=5.0,
                                            step=.05, key="cg_dscr")
consent = st.checkbox("The applicant consented to analysis of the listed documents for this credit review",
                      key="cg_consent")
if not consent:
    st.info("Consent is required before transaction analysis can run.")

st.subheader("2 · Evidence and transaction review")
reviewed_documents = st.multiselect("Document groups received and reviewed", DOCUMENTS,
                                    key="cg_documents")
document_coverage = len(reviewed_documents) / len(DOCUMENTS)
st.progress(document_coverage, text=f"Document coverage: {document_coverage:.0%}")
uploaded = st.file_uploader("Bank, MFS or marketplace statement", type=["csv", "xlsx", "pdf"],
                            help="CSV/XLSX works best. PDFs must contain selectable transaction tables.")
sheet = st.text_input("Excel worksheet name (optional)")
if uploaded and st.button("Extract transaction candidates"):
    try:
        st.session_state.cg_transactions = read_transaction_file(
            uploaded.getvalue(), uploaded.name, sheet or None)
        st.session_state.pop("cg_analysis", None)
        st.success("Candidates extracted. Review dates, signs, categories, balances and source references below.")
    except (ValueError, UnicodeDecodeError) as exc:
        st.error(str(exc))

transactions = st.session_state.get("cg_transactions")
if not isinstance(transactions, pd.DataFrame) or transactions.empty:
    st.info("Upload a statement or load the fictional case to continue.")
    st.stop()

st.caption("Positive Amount values are inflows; negative values are outflows. Extraction is assistive. Correct every material value before analysis.")
if st.button("Suggest transaction categories"):
    st.session_state.cg_transactions = suggest_transaction_categories(transactions)
    st.session_state.pop("cg_analysis", None)
    st.rerun()
reviewed_transactions = st.data_editor(
    transactions, num_rows="dynamic", hide_index=True, width="stretch", key="cg_transaction_editor",
    column_config={"Date": st.column_config.DateColumn(required=True, format="DD/MM/YYYY"),
                   "Amount": st.column_config.NumberColumn("Signed amount (BDT)", required=True),
                   "Balance": st.column_config.NumberColumn("Running balance (BDT)"),
                   "Category": st.column_config.TextColumn("Reviewed category"),
                   "Source": st.column_config.TextColumn("Source reference")})
st.session_state.cg_transactions = reviewed_transactions
with st.expander("Evidence review indicators", expanded=True):
    st.dataframe(evidence_checks(reviewed_transactions), hide_index=True, width="stretch")
    st.caption("These deterministic checks prioritize human review. They do not establish fraud, identity or repayment behavior.")

st.subheader("3 · Pricing assumptions and affordability")
rate_cols = st.columns(4)
risk_free = rate_cols[0].number_input("Risk-free reference %", min_value=0.0, max_value=100.0,
                                      step=.25, key="cg_risk_free")
operating_premium = rate_cols[1].number_input("Operating-cost premium %", min_value=0.0,
                                              max_value=100.0, step=.25,
                                              key="cg_operating_premium")
liquidity_premium = rate_cols[2].number_input("Liquidity premium %", min_value=0.0,
                                              max_value=100.0, step=.25,
                                              key="cg_liquidity_premium")
risk_premium = rate_cols[3].number_input("Credit-risk premium %", min_value=0.0,
                                         max_value=100.0, step=.25,
                                         key="cg_credit_premium")
benchmark_cols = st.columns(2)
benchmark_source = benchmark_cols[0].text_input("Risk-free source / instrument", key="cg_rate_source",
                                                placeholder="Reviewed source and tenor")
benchmark_date = benchmark_cols[1].date_input("Benchmark as-of date", max_value=date.today(),
                                              key="cg_rate_date", format="DD/MM/YYYY")
reviewed_expenses = st.number_input(
    "Reviewed average monthly operating expenses (BDT; zero uses statement-derived outflows)",
    min_value=0.0, step=1_000.0, key="cg_reviewed_expenses")

if st.button("Calculate explainable credit analysis", type="primary", disabled=not consent):
    if not benchmark_source.strip():
        st.error("Enter the reviewed risk-free source or instrument.")
    else:
        try:
            st.session_state.cg_analysis = analyze_credit(
                reviewed_transactions, requested, int(tenure), existing_debt, minimum_dscr,
                risk_free / 100, operating_premium / 100, liquidity_premium / 100,
                risk_premium / 100, document_coverage,
                None if reviewed_expenses == 0 else reviewed_expenses)
        except ValueError as exc:
            st.error(str(exc))

analysis = st.session_state.get("cg_analysis")
if analysis is None:
    st.stop()

st.divider()
st.subheader("4 · Explainable result")
score_cols = st.columns(4)
score_cols[0].metric("CredGrid score", "Withheld" if analysis.score is None else f"{analysis.score:.1f} / 100")
score_cols[1].metric("Profile band", analysis.band)
score_cols[2].metric("Evidence confidence", f"{analysis.confidence:.0%}")
score_cols[3].metric("Observed months", f"{int(analysis.profile['Months'])}")
st.caption(f"Model {CREDIT_MODEL_VERSION}. The score is a transparent pilot scorecard. It is not a credit bureau score or a predicted probability of default.")

cash_cols = st.columns(4)
cash_cols[0].metric("Average monthly inflows", f"BDT {analysis.profile['Average Monthly Inflows']:,.0f}")
cash_cols[1].metric("Reviewed monthly expenses", f"BDT {analysis.profile['Reviewed Monthly Expenses']:,.0f}")
cash_cols[2].metric("Average net cash flow", f"BDT {analysis.profile['Average Net Cash Flow']:,.0f}")
cash_cols[3].metric("Positive months", f"{analysis.profile['Positive Month Share']:.0%}")
st.bar_chart(analysis.monthly_cashflow.set_index("Month")[["Inflows", "Outflows", "Net Cash Flow"]])

component_tab, reason_tab, ledger_tab = st.tabs(["Score components", "Reason codes", "Monthly ledger"])
with component_tab:
    st.dataframe(analysis.components.style.format({"Weight": "{:.1f}", "Factor": "{:.1%}",
                                                    "Points": "{:.1f}"}), hide_index=True, width="stretch")
with reason_tab:
    for reason in analysis.reasons:
        st.write("• " + reason)
with ledger_tab:
    st.dataframe(analysis.monthly_cashflow, hide_index=True, width="stretch")

st.subheader("5 · Modeled loan proposal")
proposal = analysis.proposal
proposal_cols = st.columns(4)
proposal_cols[0].metric("Repayment capacity", f"BDT {proposal['Capacity Amount']:,.0f}")
proposal_cols[1].metric("Modeled amount", f"BDT {proposal['Recommended Amount']:,.0f}")
proposal_cols[2].metric("Monthly payment", f"BDT {proposal['Proposed Monthly Payment']:,.0f}")
proposal_cols[3].metric("Proposed annual rate", f"{proposal['Annual Proposed Rate']:.2%}")
st.write(f"Modeled post-loan DSCR: **{proposal['Post Loan DSCR']:.2f}x** · "
         f"risk-free reference: **{proposal['Risk Free Rate']:.2%}** · tenure: **{int(proposal['Tenure Months'])} months**")
st.info("This modeled amount and rate are recommendations for review. They do not establish eligibility, approval, pricing legality or contractual terms.")

inputs = {key: st.session_state.get(key) for key in [
    "cg_business_name", "cg_business_type", "cg_purpose", "cg_requested", "cg_tenure",
    "cg_existing_debt", "cg_dscr", "cg_risk_free", "cg_rate_source", "cg_documents", "cg_consent",
    "cg_operating_premium", "cg_liquidity_premium", "cg_credit_premium", "cg_reviewed_expenses"]}
inputs["cg_rate_date"] = benchmark_date.isoformat()
inputs["cg_model_version"] = CREDIT_MODEL_VERSION
save_col, report_col = st.columns(2)
if save_col.button("Save credit case", width="stretch"):
    try:
        case_id = repository().save_credit_case(
            business_name, case_payload(inputs, reviewed_transactions, analysis),
            st.session_state.get("cg_case_id"))
        st.session_state.cg_case_id = case_id
        st.success("Credit case and model inputs saved locally.")
    except ValueError as exc:
        st.error(str(exc))
report_col.download_button("Download reviewer report", report_html(
    business_name or "Unnamed business", analysis, benchmark_source, benchmark_date),
    file_name="CredGrid_Reviewer_Report.html", mime="text/html", width="stretch")

st.subheader("6 · Human decision and override record")
if not st.session_state.get("cg_case_id"):
    st.info("Save the credit case before recording a human decision.")
else:
    with st.form("credit_decision"):
        decision = st.selectbox("Human decision", ["Approve", "Modify", "Decline"])
        decision_cols = st.columns(3)
        final_amount = decision_cols[0].number_input("Final amount (BDT)", min_value=0.0,
                                                     value=float(proposal["Recommended Amount"]))
        final_tenure = decision_cols[1].number_input("Final tenure (months)", min_value=1,
                                                     max_value=60, value=int(proposal["Tenure Months"]))
        final_rate = decision_cols[2].number_input("Final annual rate %", min_value=0.0,
                                                   max_value=100.0,
                                                   value=float(proposal["Annual Proposed Rate"] * 100))
        reviewer = st.text_input("Reviewer name or staff ID")
        rationale = st.text_area("Decision rationale and any override explanation")
        confirmed = st.checkbox("I reviewed the source evidence, model limitations, applicable policy and final terms")
        submitted = st.form_submit_button("Record final human decision", disabled=not confirmed)
    if submitted:
        if final_rate / 100 <= proposal["Risk Free Rate"] and decision != "Decline":
            st.error("The final lending rate must be higher than the reviewed risk-free reference rate.")
        else:
            try:
                decision_id = repository().save_credit_decision(
                    st.session_state.cg_case_id, decision, reviewer, rationale,
                    {"amount": final_amount, "tenure_months": final_tenure,
                     "annual_rate": final_rate / 100, "model_score": analysis.score,
                     "model_amount": proposal["Recommended Amount"]})
                st.success(f"Human decision recorded in audit entry #{decision_id}.")
            except ValueError as exc:
                st.error(str(exc))

    history = repository().credit_decisions(st.session_state.cg_case_id)
    if history:
        st.dataframe(pd.DataFrame(history).drop(columns=["payload"], errors="ignore"),
                     hide_index=True, width="stretch")
