"""Same-industry listed-company and uploaded-statement comparison workspace."""
import pandas as pd
import streamlit as st

from components.formatting import fmt, unit_for
from components.ui import cached_analysis, header
from core.comparison_engine import (EXCHANGE_METRICS, comparison_strengths,
                                    exchange_metric_comparison)
from data.industry_catalog import INDUSTRY_TICKERS, industry_for_ticker, suggested_peers
from data.market_data import bundled_ticker_catalog, exchange_financials
from data.parsers import prepare, read_file


header("Industry Comparison", "Choose an anchor company, add suggested same-industry peers and compare exchange or uploaded financial data.")
st.warning("Comparison support only. Verify sector membership, fiscal year-ends, accounting policies, units and source dates before drawing conclusions.")


@st.cache_data(ttl=900, show_spinner=False)
def cached_financials(exchange: str, ticker: str):
    return exchange_financials(exchange, ticker)


exchange = st.selectbox("Exchange", ["DSE", "CSE"], key="comparison_exchange")
catalog = bundled_ticker_catalog(exchange)
catalog_options = list(catalog) or sorted({ticker for values in INDUSTRY_TICKERS.values() for ticker in values})
default_anchor = "OLYMPIC" if "OLYMPIC" in catalog else catalog_options[0]
anchor = st.selectbox(
    "Anchor company", catalog_options, index=catalog_options.index(default_anchor),
    accept_new_options=True, filter_mode="fuzzy",
    format_func=lambda ticker: f"{ticker} — {catalog.get(ticker, '')}" if catalog.get(ticker) else ticker,
    help="Type a ticker or company name. Olympic Industries is selected initially as an example.")
anchor = str(anchor).strip().upper()
detected = industry_for_ticker(anchor)
industries = list(INDUSTRY_TICKERS)
industry = st.selectbox("Industry group", industries,
                        index=industries.index(detected) if detected in industries else 0,
                        help="Packaged groups provide offline suggestions. Confirm membership against the exchange profile.")
suggestions = suggested_peers(anchor, industry, set(catalog))
st.caption(f"Suggested {industry} peers for {anchor}: " +
           (", ".join(suggestions) if suggestions else "none in the packaged ticker snapshot"))
selected = st.multiselect(
    "Comparison companies", suggestions,
    default=suggestions[:3], max_selections=7,
    format_func=lambda ticker: f"{ticker} — {catalog.get(ticker, '')}" if catalog.get(ticker) else ticker)
manual = st.text_input("Additional tickers (optional, comma-separated)",
                       help="Use this when a company is missing from the packaged suggestions.")
manual_tickers = [item.strip().upper() for item in manual.split(",") if item.strip()]
tickers = list(dict.fromkeys([anchor] + selected + manual_tickers))
if len(tickers) > 8:
    st.error('Choose at most eight companies, including the anchor and additional tickers.')
st.write("**Comparison set:** " + " · ".join(tickers))

exchange_tab, upload_tab = st.tabs(["Exchange-provided metrics", "Uploaded full statements"])
with exchange_tab:
    st.caption("The exchanges provide a limited annual summary. Missing metrics remain blank; the app does not estimate them.")
    comparison_key = (exchange, tuple(tickers))
    if st.session_state.get('industry_exchange_key') != comparison_key:
        if st.session_state.get('industry_exchange_details'):
            st.info('The comparison set changed. Load exchange comparison to refresh the companies shown.')
        for state_key in ('industry_exchange_details', 'industry_exchange_sources', 'industry_exchange_failures'):
            st.session_state.pop(state_key, None)
    if st.button("Load exchange comparison", type="primary", disabled=not 2 <= len(tickers) <= 8):
        loaded, failures, sources = {}, [], {}
        for ticker in tickers:
            try:
                result = cached_financials(exchange, ticker)
                loaded[ticker] = result.details
                sources[ticker] = {"source": result.source_url, "fetched_at": result.fetched_at}
            except ValueError as exc:
                failures.append(f"{ticker}: {exc}")
        st.session_state.industry_exchange_details = loaded
        st.session_state.industry_exchange_sources = sources
        st.session_state.industry_exchange_failures = failures
        st.session_state.industry_exchange_key = comparison_key
    for failure in st.session_state.get("industry_exchange_failures", []):
        st.warning(failure)
    details = st.session_state.get("industry_exchange_details", {})
    if details:
        common_years = set.intersection(*[
            set(pd.to_numeric(frame["Year"], errors="coerce").dropna().astype(int))
            for frame in details.values()])
        all_years = sorted({year for frame in details.values()
                            for year in pd.to_numeric(frame["Year"], errors="coerce").dropna().astype(int)},
                           reverse=True)
        year_options = sorted(common_years, reverse=True) or all_years
        year = st.selectbox("Comparison fiscal year", year_options,
                            help="A common year is preferred. If none exists, missing company values stay blank.")
        comparison = exchange_metric_comparison(details, year)
        formatters = {"Net Income": "{:,.1f}", "Basic EPS": "{:,.2f}",
                      "NAV per Share": "{:,.2f}", "Dividend": "{:.2f}%",
                      "Cash Dividend": "{:.2f}%", "Stock Dividend": "{:.2f}%",
                      "Dividend Yield": "{:.2f}%"}
        st.dataframe(comparison.style.format(formatters, na_rep="N/A"), width="stretch")
        st.caption('Cash and stock dividend percentages are separate. A combined dividend is shown only when the source reports a total or both components.')
        chart_metric = st.selectbox("Chart metric", EXCHANGE_METRICS,
                                    index=EXCHANGE_METRICS.index("Basic EPS"))
        st.bar_chart(pd.to_numeric(comparison[chart_metric], errors="coerce"))
        st.markdown("**Metric reference leaders**")
        leaders = comparison_strengths(
            comparison.drop(columns=["Year"], errors="ignore"),
            ["Net Income", "Basic EPS", "NAV per Share", "Dividend", "Dividend Yield"])
        st.dataframe(leaders, hide_index=True, width="stretch")
        with st.expander("Sources and retrieval times"):
            st.dataframe(pd.DataFrame.from_dict(
                st.session_state.get("industry_exchange_sources", {}), orient="index")
                .rename_axis("Ticker").reset_index(), hide_index=True, width="stretch")

with upload_tab:
    st.caption("Upload one values-only Falcon Finalysis CSV/XLSX per company. Filenames become company labels. Up to 20 companies are supported.")
    uploads = st.file_uploader("Company statement files", type=["csv", "xlsx"],
                               accept_multiple_files=True, key="industry_uploads")
    uploads = uploads or []
    include_active = st.checkbox("Include the active Falcon Finalysis project",
                                 value="frame" in st.session_state,
                                 disabled="frame" not in st.session_state)
    analyses = {}
    if include_active and "frame" in st.session_state:
        analyses[st.session_state.get("meta", {}).get("company_name", "Active company")] = cached_analysis(
            st.session_state.frame, st.session_state.get("tolerance", .01))
    if len(uploads) + len(analyses) > 20:
        st.error("Select at most 20 companies, including the active project.")
    else:
        for upload in uploads:
            try:
                label = upload.name.rsplit(".", 1)[0]
                if label in analyses:
                    st.error(f"{upload.name}: duplicate company label. Rename the file before comparing.")
                    continue
                analyses[label] = cached_analysis(
                    prepare(read_file(upload.getvalue(), upload.name)), .01)
            except ValueError as exc:
                st.error(f"{upload.name}: {exc}")
    if len(analyses) >= 2:
        shared_years = set.intersection(*[set(item.combined.index) for item in analyses.values()])
        if shared_years:
            compare_year = st.selectbox("Common fiscal year", sorted(shared_years, reverse=True),
                                        key="industry_uploaded_year")
            ratio_metrics = ["Revenue Growth", "Net Profit Margin", "ROA", "ROE",
                             "Current Ratio", "Debt-to-Equity", "Interest Coverage",
                             "Asset Turnover", "Cash Conversion Cycle"]
            ratio_rows = {name: analysis.combined.loc[compare_year, ratio_metrics]
                          for name, analysis in analyses.items()}
            ratios = pd.DataFrame(ratio_rows).T
            formatted = ratios.astype(object)
            for metric in ratio_metrics:
                formatted[metric] = [fmt(value, unit_for(metric)) for value in ratios[metric]]
            st.dataframe(formatted, width="stretch")
            chosen_metric = st.selectbox("Visual comparison metric", ratio_metrics,
                                         key="industry_uploaded_metric")
            st.bar_chart(pd.to_numeric(ratios[chosen_metric], errors="coerce"))
            leaders = comparison_strengths(
                ratios, ["Revenue Growth", "Net Profit Margin", "ROA", "ROE",
                         "Current Ratio", "Interest Coverage", "Asset Turnover"])
            st.dataframe(leaders, hide_index=True, width="stretch")
        else:
            st.warning("The uploaded companies do not share a fiscal-year label. Align periods before comparing.")
    elif uploads:
        st.info("Upload at least two valid company files, or include an active project plus one upload.")

st.caption("Reference leaders are shown one metric at a time. Falcon Finalysis does not produce a composite company ranking or investment recommendation.")
