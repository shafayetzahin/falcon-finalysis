# Falcon Finalysis implementation plan

## Architecture
Streamlit presentation → analysis service → pure calculation/rule modules.
Upload adapters normalize labels without overwriting source values. SQLite stores
company metadata, project versions, annual statements, metrics, scenarios and report history.
Report builders consume the same analysis result as the UI. Optional, bounded connectors read public
DSE/CSE pages for a user-selected ticker/date range; statement data and projects remain local.
The portfolio engine applies dated corporate actions to price histories and calculates
holding-period and periodic risk/return measures with aligned observations. Portfolio workspaces are
stored as version-tolerant JSON payloads in the local SQLite database; no portfolio data leaves the device.
The separate CredGrid engine normalizes reviewed transactions, computes disclosed scorecard components and
models DSCR-constrained capacity with benchmark-plus-premium pricing. It cannot issue an automatic decision.
The data-quality engine scores completeness and provenance, identifies structural and reconciliation
issues, and produces a remediation queue without modifying source values. Portfolio decision helpers
decompose risk and build deterministic long-only opportunity and rebalancing tables.
The valuation engine keeps WACC, FCFF discounting, terminal value, equity bridge, sensitivity,
trading-comps and ROIC/reinvestment calculations independent from Streamlit. The Valuation Lab
uses only reviewed project values and explicit market assumptions.
The comparison engine aligns fiscal years and builds per-metric reference leaders, while the packaged
industry catalog supplies offline peer suggestions. The Industry Comparison page combines these with
the existing DSE/CSE adapters and statement parser.

## Repository
`app.py`, `pages/`, `components/`, `core/`, `data/`, `reports/`, `assets/`, `tests/`, `docs/`.

## Dependencies
Python 3.11+, Streamlit, pandas, NumPy, Plotly, openpyxl, ReportLab, pdfplumber, Requests;
pytest and Ruff for QA. SQLite uses Python's standard library. XLSX, UTF-8 CSV and text-based
PDF statement tables are supported; legacy XLS is rejected with conversion guidance.

## Core schema
One row per full fiscal year (3–10 consecutive years), integer `Year`, numeric statement fields in full currency units.
Expense, capex and dividend amounts are positive magnitudes; cash flow statements use signed flows.
Missing values remain unavailable, never zero-filled. Weighted Average Shares Outstanding is separate from ending Shares Outstanding.
First-year average-balance ratios use ending balances and are explicitly labelled. Later years require both balances.
Companies → Projects → FinancialPeriods → FinancialStatements; CalculatedMetrics, ScenarioModels and ReportHistory reference Projects.
PortfolioProjects stores portfolio payloads. CreditCases stores versioned case inputs and CreditDecisions
stores append-only reviewer outcomes and rationale.
ImportMappings stores reusable reviewed column mappings. AppSettings and AuditEvents support the local
governance view; they do not replace production authentication, encryption or centralized audit controls.

## Milestones
1. Schema, validation, parsers and storage.
2. Ratios, growth, DuPont and tests with independent expected values.
3. Transparent health score, contextual interpretations and risk/positive signals.
4. Streamlit pages, demo data, project actions and manual mapping/editor workflows.
5. Explicit one-year scenario model and sensitivity analysis.
6. PDF/Excel outputs, documentation, integration tests and visual review.
7. Official DSE/CSE lookup, market-history workbook and review-first document extraction.
8. Multi-stock portfolio analysis with dividends, rights, splits and covariance.
9. Saved holdings, fees, benchmark context, downside risk measures and reviewable portfolio output.
10. CredGrid pilot transaction intake, explainable scorecard, affordability proposal and human decision log.
11. Data-quality center, reusable import mappings, portfolio decision tools and local governance controls.
12. Selected-company Valuation Lab with WACC, ROIC, DCF sensitivity, comps and football-field output.
13. Same-industry company comparison with suggested tickers, exchange summaries and uploaded statements.

## Financial policies
Positive denominators are required for conventional ratios. Negative numerators remain meaningful.
Growth over nonpositive bases is unavailable. CAGR requires positive endpoints and uses elapsed years.
CCC = inventory days + receivable days - payable days (the pasted list's multiplication marker is a formatting ambiguity).
Revenue proxies credit sales and COGS proxies credit purchases. All ratios use full-year 365-day periods.
Health scoring exposes missing-data coverage and withholds an overall score unless all categories have evidence and at least 75% of weighted inputs exist.
Scenario ROA/ROE use explicitly frozen balance-sheet denominators; cash flow is a simplified proxy, not a balanced three-statement forecast.
