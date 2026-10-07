# Falcon Finalysis verification record — 07/10/2026

Verified on Windows with Python 3.12, Streamlit 1.63.0, pandas 3.0.1,
NumPy 2.3.5, Plotly 7.0.0, openpyxl 3.1.5 and ReportLab 4.4.9.
The runtime and development requirement files were installed successfully into
the workspace test environment. Python 3.11 is the minimum target; that separate
interpreter version was not available for a second platform run.

## Automated coverage

**237 pytest cases** cover:

- Independent expected current/quick/cash/OCF ratios, margins, ROA/ROE,
  debt/equity vs liabilities/equity, interest coverage, turnover, operating days,
  CCC, FCF and per-share ratios.
- First-year fallback, missing opening balances, zero interest/liabilities,
  negative equity and unavailable reasons.
- DuPont equality and exact attribution sum; positive-endpoint CAGR and invalid growth bases.
- Health score best/worst bounds, coverage and sparse-input withholding.
- Base scenario and +15% growth known values, OCF proxy, day-driver sensitivity and invalid assumptions.
- Fictional demo income, balance sheet and cash reconciliations.
- Duplicate, missing, fractional and nonfinite years/values; text input rejection.
- CSV aliases and SQLite create/reopen/duplicate/rename/delete across repository instances.
- Formula-containing XLSX rejection, corrupted XLSX, legacy XLS guidance and empty-file errors.
- XLSX input round trip, required export sheets, freeze panes, chart presence,
  numerical types, formula injection neutralization and error-cell scan.
- PDF generation, required sections, page count and readable extracted text.
- Every application page through Streamlit AppTest, demo toggle, dark workspace,
  manual editor application with preserved warnings, project save, +15% scenario,
  scenario save, demo-to-Overview routing and PDF/Excel generation.
- Ten-year statement processing across twenty analysis runs and ten-year PDF export.
- Sparse-input PDF/Excel generation without invented financial ratios or scores.
- Values-only statement-layout extraction, PDF table/text fallback, unit scaling and source-page evidence.
- DSE-style price normalization, manual price-file fallback and the four-sheet market-data workbook.
- DSE/CSE annual-metric parsing and conservative Excel prefill that copies only directly reported values.
- Searchable DSE/CSE ticker suggestions, CSE market-suffix normalization and manual ticker entry.
- Analysis readiness, missing-field explanations, provenance merge behavior and SQLite provenance persistence.
- Portfolio holding-period returns with cash dividends, stock dividends, rights issues and splits;
  periodic average return, standard deviation, variance, covariance and normalized portfolio weights.
- Holdings and transaction-cost valuation, Sharpe/Sortino ratios, maximum drawdown, historical VaR,
  and local saved-portfolio create/open/rename/duplicate/delete behavior.
- CredGrid signed transaction normalization, evidence-based score components, insufficient-history
  withholding, benchmark-plus-premium pricing, DSCR-constrained capacity and human-decision audit storage.
- CredGrid fictional case UI, modeled proposal rendering and mandatory human-review language.
- Data-quality scoring, reusable import mappings, local settings and governance audit records.
- Portfolio risk contribution, simulated opportunity set and value-based rebalancing math.
- Every registered page, including Data Quality Center and Local Governance.
- WACC, FCFF DCF, enterprise-to-equity bridge, sensitivity, trading-comps and ROIC/reinvestment math.
- Valuation Lab calculation and football-field rendering through Streamlit AppTest.
- Industry suggestion lookup, common-year exchange alignment and the registered comparison page.

Ruff checks and Python compilation also pass.

The October reliability audit added independent regressions for numeric-prefix corruption,
scientific notation, duplicate/formula/oversized spreadsheet uploads, invalid transaction rows,
CSE identity and profile labels, cash/stock dividend distinctions, common portfolio intervals,
initial-capital drawdown, risk-free downside targets, missing credit months, excluded financing
receipts, debt-service double counting, finite valuation assumptions, recovery integrity,
consistent SQLite WAL backups, source corrections and stale UI results. UI tests verify changed
inputs remove exports, withdrawn consent removes credit results, new portfolios reset holding
edits, new companies require fresh valuation confirmation, and human review is checked at submission.
See [AUDIT_2026-10-07.md](AUDIT_2026-10-07.md) for this release's changes and limits.

## Live application checks

On 07/10/2026, official connector checks returned DSE SQURPHARMA and OLYMPIC company
details, eight annual years (2018–2025), and 26 dated price rows each for
01/09/2026–06/10/2026. CSE SQURPHARMA returned five annual years (2021–2025) and
25 price rows, with its last returned date 05/10/2026. The missing final requested
date is disclosed as source coverage, not filled in. CSE company identity and dividend
markers were verified again after the parser repair. The local staging browser verified
the dismissible first-session notice, the complete-demo button, chart/metric rendering,
light/dark navigation and readable dropdown options. Caption opacity and help-icon
stroke colors were repaired based on computed browser styles and screenshots.

The following paragraphs record earlier delivery checks, not an additional current device run.

The app started successfully on `127.0.0.1:8501`. Browser inspection verified the
first-session decision-support notice, its dismiss control, landing page, demo loading,
actual Plotly chart elements, summary metrics and the
light/dark dashboard. The Listed Company Data page was also checked with a live
DSE `SQURPHARMA` company lookup and 90-day history fetch; 61 records, chart,
metrics, table and Excel download control rendered. Direct connector checks also
returned DSE and CSE date-range histories. Visual review caught and corrected narrow metric cards and
dark-theme contrast issues, including selected, hover and default sidebar menu states. The beginner
onboarding, listed-company template flow and three-logo gallery were also inspected. A fictional demo
project was saved locally. The Portfolio Management page was exercised with its fictional
three-stock example, including corporate actions, holding-period results, risk statistics,
covariance table and heatmap. A clean browser session also verified holdings and fee inputs,
risk-free-rate entry, benchmark comparison, advanced risk metrics and the HTML report control.
The CredGrid AI pilot was then exercised in a clean browser session with its fictional small-business
case. The consent gate, document coverage, editable transactions, six disclosed score components,
reason codes, monthly ledger, DSCR-constrained loan capacity, benchmark-plus-premium pricing,
reviewer report control and separate human-decision boundary all rendered without application errors.
The Valuation Lab was exercised with the five-year fictional company. WACC, ROIC/reinvestment,
FCFF forecast, DCF enterprise/equity values, value-per-share sensitivity and the football-field
summary rendered from an explicitly dated assumption source.
The development server is bound to localhost; it is not a cloud deployment.

## Report verification

The final Apex example PDF has **18 pages**. Pages were rendered with PyMuPDF and
visually reviewed. Formula-reference pagination was corrected to remove a short
spillover page. Vector charts, section headings, page numbers and tables render.
The PDF contains only fictional demonstration figures.

The example Excel workbook has **19 sheets**, including Data Sources. It was reopened with openpyxl;
sheet structure, numeric values, formats, panes and chart bindings were checked.
Wrapped row heights were adjusted after specialized column widths to prevent
truncated notes and signal evidence. Read-only layout previews derived from saved
cell styles were reviewed for every sheet's leading area.

## Verification limits

- Microsoft Excel itself was not automated. The optional artifact renderer did not
  produce a usable render in this environment. Cell-style previews are approximations,
  not proof of native Excel pixel layout. The workbook was successfully reopened and
  structurally validated; native Excel appearance remains a user-side check.
- Streamlit AppTest exercises UI logic, not every browser/device combination.
  Upload parsing and mapping are tested through the same adapters used by the UI;
  a native operating-system file-picker interaction was not included.
- Twenty-company coverage is a bounded functional workload, not a measured service-level guarantee.
- Test data is synthetic. No independent accountant or external financial audit has certified the model.

## Reproduce

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
python -m compileall -q app.py core data components pages reports
python scripts/generate_demo.py
python -m streamlit run app.py
```
