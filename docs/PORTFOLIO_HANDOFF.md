# Falcon Finalysis delivery and portfolio guide

## 1. What was built

A modular Streamlit application with 22 views for company setup, listed-company lookup, statement
analysis, financial ratios, DuPont, working capital, cash flow, multi-year trends,
peer comparison, deterministic insights, transparent financial health scoring,
operating scenarios and PDF/Excel reporting. SQLite saves projects and scenario
assumptions. Fictional Apex demo data and generated example reports are included.

## 2. Folder structure

`app.py` is the entry point. `core/` owns calculations and policies; `data/` owns
parsers, demo generation and SQLite; `components/` owns reusable presentation;
`pages/` contains views; `reports/` produces exports; `tests/` contains regression
checks; `docs/` contains methodology and handoff; `examples/` contains demo reports.
See README and ARCHITECTURE for the complete tree and database schema.

## 3. Installation

From the `finsight` folder, with Python 3.11+:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Use `py -3` for the first command if Windows exposes the Python launcher instead.
On macOS/Linux, use `.venv/bin/python` for subsequent commands.

## 4. Run

```powershell
.venv\Scripts\python -m streamlit run app.py
```

Visit http://127.0.0.1:8501. No API keys are needed. Stop with Ctrl+C in the terminal.
The development preview launched during delivery uses a workspace test environment;
the commands above create your own portable environment after copying the repository.

## 5. Demo workflow

Load Demo Company → Overview → Ratio Analysis → DuPont Analysis → Working Capital →
Key Insights & Risk Flags → Scenario Lab (Revenue Growth 15%) → Save project →
Generated Report → Generate PDF & Excel → Download. Restart the application and
open the saved company through Projects & Data → Saved projects.

Portfolio Demo Mode automatically loads Apex; it uses no private company information.
The demo shows revenue growth and improved OCF alongside margin compression and a
longer cash cycle. The latest generic health score is 80.0 / 100 with full coverage.

## 6. Formulas implemented

Liquidity: current, quick, cash and OCF ratios; net working capital.
Profitability: gross, operating, EBITDA and net margins; ROA, ROE and ROCE.
Efficiency: asset, inventory, receivables and payables turnover; inventory,
receivable and payable days; CCC.
Funding: total debt, debt/equity, liabilities/equity, debt ratio, long-term
debt/capital, interest coverage and optional cash interest coverage.
Cash: FCF, OCF margin, OCF/net income and capex intensity.
Market: EPS, P/E, book value/share, price/book, payout and dividend yield.
Analysis: YoY, CAGR, horizontal/common-size analysis, DuPont factors and attribution,
trend direction/volatility, health scores, operating scenarios and sensitivity.

Exact formulas, inputs, assumptions and edge cases: FORMULAS.md.

## 7. Verification

Financial expected-value tests cover the requested ratio list, first-year and
average-balance policies, missing/zero/negative inputs, CAGR, DuPont equality,
score boundaries and scenario results. Integration checks cover import round trips,
formula rejection, SQLite lifecycle, PDF structure, Excel sheets/styles, all UI
pages and a save/scenario/report workflow. See QA.md for final counts and limitations.

## 8. Known limitations

The current build supports 3–10 consecutive annual periods, values-only XLSX/CSV,
review-first text-PDF extraction and the supplied schema. Scenario cash flows and returns are simplified proxies. Generic scoring is
not predictive or an industry credit rating. Excel exports are numerical snapshots.
Peers are uploaded per session. Public DSE/CSE company facts and historical prices are
available with an upload fallback. Portfolio analysis, DCF valuation, industry comparison and a
CredGrid cash-flow credit pilot are included. The public Streamlit demo uses temporary session storage.
Managed sign-in and persistent private workspace setup are prepared; provider activation, encrypted
hosting and scheduled backups require deployment configuration. OCR and external generative AI are
not included. See README, ACCOUNT_SETUP.md and QA.md for current capabilities and limits.

## 9. Recommended V1.1

1. Opening-balance inputs and multiple fiscal-year conventions.
2. Industry-specific benchmark profiles with documented sources.
3. Persistent import mappings and additional statement layouts.
4. Linked income/balance/cash-flow forecasting with scenario version comparisons.
5. Broader business-model fixtures and international PDF typography.

## 10. Screens to capture

| Screen | What it demonstrates |
|---|---|
| Overview | Executive communication, finance KPIs and restrained visual design |
| Risk Flags with evidence expanded | Deterministic reasoning and investigation questions |
| DuPont Analysis | Understanding of returns, operations and capital structure |
| Working Capital | Connection between accounting performance and funding needs |
| Scenario Lab at +15% growth | Financial modelling and interactive decision support |
| Sensitivity tornado | Quantitative comparison of operating drivers |
| PDF cover/summary and Excel ratios | Automated professional reporting |

Capture only fictional demo data, at a readable desktop width. Prefer 4–6 focused
images over a long, illegible full-page screenshot. Pair each image with one sentence
about the analytical question it answers. Do not claim a screenshot proves model accuracy.

## 11. 60-second interview explanation

“Falcon Finalysis is a local financial analytics application that turns annual statements
into structured analysis. It combines Python, pandas, Streamlit and SQLite with
financial ratios, DuPont decomposition, working-capital analysis and scenario modelling.

The key design choice is to connect calculations with interpretation. For example,
the demo company grows revenue and operating cash flow, but its collection cycle
lengthens and margins compress. The application surfaces those tensions and offers
questions to investigate rather than issuing investment recommendations.

Financial correctness is explicit: debt and liabilities are separate, return ratios
use average balances, missing data stays unavailable, and every scenario states its
assumptions. I can trace the formulas and explain the automated tests. The final
workflow saves projects locally and produces consistent PDF and Excel reports.
It demonstrates how finance knowledge, data validation and software engineering can
support a practical analyst workflow.”

Use first-person wording only for work you can truthfully explain and stand behind.
Be ready to describe any development assistance and the decisions you personally made.

## 12. Suggested CV project description

**Falcon Finalysis — Financial Analytics & Decision Support | Python, Streamlit, pandas, Plotly, SQLite**

- Developed a local financial-analysis workflow covering annual statement imports,
  ratios, DuPont, working-capital trends, transparent health scoring and rule-based insights.
- Implemented operating scenarios and sensitivity analysis with explicit cash-flow
  assumptions, plus automated PDF/Excel exports and local project persistence.
- Validated calculations with known-value financial tests and exercised data, storage,
  export and Streamlit workflows through automated regression checks.

Adjust “developed” and “implemented” to reflect your actual contribution. Add the final
test count only if you can reproduce it. Avoid claims of predictive credit accuracy,
investment performance or commercial adoption.

## 13. Suggested GitHub repository description

Local-first financial analytics in Python: statement imports, ratios, DuPont,
working capital, explainable insights, scenario analysis and PDF/Excel reporting.

## 14. Suggested LinkedIn project description

Falcon Finalysis explores the intersection of corporate finance, data analytics and software
development. It turns annual financial statements into an interactive analyst workspace
with profitability, liquidity, leverage, cash-flow and working-capital analysis.

The project includes a fictional five-year manufacturer, transparent rule-based
interpretations, a documented financial health score, operating scenarios, sensitivity
analysis and automated reporting. It runs locally without external AI or paid APIs.

My focus is on making the analytical reasoning inspectable: explicit formulas,
data-quality checks, careful missing-data handling and tested calculations. It is an
educational decision-support project, not an investment recommendation or credit-rating system.

Personalize the final paragraph with your contribution, one challenge you solved and
a link to the public repository only after you publish it.
