# Financial formula reference

First-year average-balance ratios use ending balances because opening balances are unavailable. Later years use the mean of consecutive opening and closing balances. Revenue proxies credit sales; COGS proxies purchases. Full fiscal years use 365 days.

## Shared policies

All inputs are finite annual reported numbers in full currency units. Missing dependencies produce N/A; zero is never inferred. Conventional denominators must be strictly positive. Negative numerators (for example losses) remain meaningful. Return ratios require positive equity at both ends. No subtotal is silently derived or overwritten. Percent ratios are stored as decimals. Money units are distinct from ratios and days.

## Registered metrics

| Metric | Inputs / dependencies | Formula | Unit |
|---|---|---|---|
| Current Ratio | Total Current Assets, Total Current Liabilities | Current assets / current liabilities | x |
| Quick Ratio | Total Current Assets, Inventory, Total Current Liabilities | (Current assets - inventory) / current liabilities | x |
| Cash Ratio | Cash, Total Current Liabilities | Cash / current liabilities | x |
| Operating Cash Flow Ratio | Operating Cash Flow, Total Current Liabilities | Operating cash flow / current liabilities | x |
| Gross Profit Margin | Gross Profit, Revenue | Gross Profit / revenue | % |
| Operating Margin | EBIT, Revenue | EBIT / revenue | % |
| EBITDA Margin | EBITDA, Revenue | EBITDA / revenue | % |
| Net Profit Margin | Net Income, Revenue | Net Income / revenue | % |
| ROA | Net Income, Average Total Assets | Net income / average total assets | % |
| ROE | Net Income, Average Shareholders Equity | Net income / average equity | % |
| ROCE | EBIT, Total Assets, Total Current Liabilities | EBIT / (total assets - current liabilities) | % |
| Asset Turnover | Revenue, Average Total Assets | Revenue / average total assets | x |
| Inventory Turnover | COGS, Average Inventory | COGS / average inventory | x |
| Receivables Turnover | Revenue, Average Accounts Receivable | Revenue / average accounts receivable | x |
| Payables Turnover | COGS, Average Accounts Payable | COGS / average accounts payable | x |
| Inventory Days | Average Inventory, COGS | 365 × average inventory / COGS | days |
| Receivable Days | Average Accounts Receivable, Revenue | 365 × average accounts receivable / Revenue | days |
| Payable Days | Average Accounts Payable, COGS | 365 × average accounts payable / COGS | days |
| Cash Conversion Cycle | Inventory Days, Receivable Days, Payable Days | Inventory days + receivable days - payable days | days |
| Net Working Capital | Total Current Assets, Total Current Liabilities | Current assets - current liabilities | money |
| Total Debt | Short-Term Debt, Long-Term Debt | Short-term debt + long-term debt | money |
| Debt-to-Equity | Total Debt, Shareholders Equity | Interest-bearing debt / ending equity | x |
| Liabilities-to-Equity | Total Liabilities, Shareholders Equity | Total liabilities / ending equity | x |
| Debt Ratio | Total Liabilities, Total Assets | Total liabilities / total assets | % |
| Long-Term Debt to Capital | Long-Term Debt, Shareholders Equity | Long-term debt / (long-term debt + equity) | % |
| Interest Coverage | EBIT, Interest Expense | EBIT / interest expense | x |
| Cash Interest Coverage | Operating Cash Flow, Cash Interest Paid, Cash Taxes Paid | (OCF + cash interest + cash taxes) / cash interest; assumes OCF includes these payments | x |
| Free Cash Flow | Operating Cash Flow, Capital Expenditure | Operating cash flow - positive capital expenditure | money |
| Operating Cash Flow Margin | Operating Cash Flow, Revenue | Operating cash flow / revenue | % |
| Cash Flow to Net Income | Operating Cash Flow, Net Income | Operating cash flow / positive net income | x |
| Capex Intensity | Capital Expenditure, Revenue | Positive capital expenditure / revenue | % |
| EPS | Net Income, Preferred Dividends, Weighted Average Shares Outstanding | (Net income - preferred dividends) / weighted average shares | money |
| P/E Ratio | Market Price Per Share, EPS | Market price / positive EPS | x |
| Book Value Per Share | Shareholders Equity, Shares Outstanding | Positive equity / ending shares | money |
| Price-to-Book | Market Price Per Share, Book Value Per Share | Market price / positive book value per share | x |
| Dividend Payout Ratio | Cash Dividends, Net Income | Cash dividends / positive net income | % |
| Dividend Yield | Shares Outstanding, Cash Dividends, Market Price Per Share | (Cash dividends / ending shares) / market price | % |

## Metric-specific assumptions and edge cases

- Average inputs = (prior year + current year) / 2. The first year uses the current ending value. Later missing balances remain unavailable.
- ROCE uses ending assets less ending current liabilities, not average capital employed.
- Quick assets exclude inventory but include other current assets; prepaid amounts are not separately supplied.
- Debt is interest-bearing short-term plus long-term debt. Total liabilities includes debt and other obligations and remains separate.
- Average equity is invalid when either adjacent equity is nonpositive, even if the arithmetic mean would be positive.
- EPS requires explicit preferred dividends and weighted average shares. Ending shares are never substituted. Book value/share requires positive equity.
- Dividend yield approximates dividends per share using ending shares. It is not a forward dividend yield.
- P/E is N/A for nonpositive EPS. Price/book is N/A for nonpositive book value. Payout and cash conversion to income are N/A for nonpositive net income.
- Interest coverage with zero interest is N/A, not infinity. Cash interest coverage needs explicit cash interest/taxes and assumes OCF includes those payments.
- Capex is a positive outflow magnitude. Negative capex or expense inputs trigger review warnings; source values are not repaired.
- Days use revenue as a credit-sales proxy and COGS as a credit-purchases proxy. Business-model differences can limit interpretation.

## Growth, trend and statement formulas

- YoY = (current - prior) / prior, available only when the prior value is positive.
- CAGR = (ending / beginning)^(1 / elapsed fiscal years) - 1. At least three complete observations and positive endpoints are required. Negative or missing endpoints produce N/A.
- Horizontal absolute change = value - selected base-year value. Percentage change divides by a strictly positive base.
- Income common size = each income item / positive revenue. Balance common size = each balance item / positive total assets.
- Trend uses the last three observations. Scale = max(abs(first), abs(mean), 1e-9). Two sequential scaled movements above 0.5% establish improvement; below -0.5% establish deterioration. A cumulative 20% magnitude is strong. Mixed paths within 5% cumulative magnitude are stable; other mixed paths are labelled mixed.
- Lower is treated as favorable for debt/equity, liabilities/equity, debt ratio, inventory days, receivable days and CCC. Other directional labels require financial context.
- Volatility = population standard deviation of the latest three levels / absolute mean, floored at 1e-9. Near-zero means can produce large indicators.

## DuPont and attribution

ROE = (net income / revenue) x (revenue / average assets) x (average assets / average equity). Positive revenue, assets and equity are required for the decomposition. Factors can be unavailable even when a standalone return has meaning.

Attribution replaces old factors with new factors in each of the six possible orders. Each factor receives its mean marginal contribution. The contributions add exactly to the change in DuPont ROE when all factors exist.

## Scenario equations

Revenue = latest revenue x (1 + assumed growth). COGS = revenue x COGS ratio. Cash operating expense = revenue x opex ratio. EBITDA = revenue - COGS - opex. EBIT = EBITDA - fixed latest depreciation. Interest = assumed debt x interest rate. Tax = max(EBIT - interest, 0) x tax rate. Net income = EBIT - interest - tax.

Receivables = revenue / 365 x receivable days. Inventory = COGS / 365 x inventory days. Payables = COGS / 365 x payable days. Operating working capital = receivables + inventory - payables. OCF proxy = net income + depreciation - change in operating working capital. FCF proxy = OCF proxy - capex. CCC = inventory days + receivable days - payable days.

Scenario ROA and ROE divide by fixed latest assets and equity, respectively; debt/equity divides assumed debt by fixed equity. Interest coverage requires positive assumed interest. These are simplified model outputs, not a reconciled projected balance sheet. Baseline rates derive from latest figures; baseline tax rate is bounded to 0–100% and is zero for nonpositive EBT. Zero-debt baseline interest rate is zero.

Sensitivity changes one driver at a time: revenue growth and gross margin +/-5pp, opex ratio +/-3pp, interest rate +/-2pp, receivable/inventory days +/-10. Bounds may make shocks asymmetric; the table displays the actual shock values.

## Health and rules

The Health Score Methodology page exposes every threshold. The central POLICY in core/health_score.py allocates category weights equally to two metrics, interpolates linearly and clips each metric to 0–100. The overall score is normalized over observed weights only when weighted coverage is at least 75% and all categories have evidence. Revenue Stability uses the population standard deviation of two annual growth rates.

Risk flags use documented generic thresholds in core/risk_engine.py. They are questions for investigation, not causal findings, predictions, credit ratings or advice.

## Portfolio return and risk

- Holding cost = starting shares × purchase price + purchase fees + rights subscriptions.
  Ending value includes dated stock dividends, splits and subscribed rights; cash dividends remain cash.
  Total gain = ending value + received cash dividends - holding cost - estimated sale fees.
  Holding-period dividend yield = cash dividends / holding cost; total return = total gain / holding cost.
- Portfolio risk first aligns common closing-price dates. Each asset's interval return covers the
  same observed start/end dates, with dated corporate actions included. Periodic returns compound
  within calendar week/month bins. A bin with no observations is unavailable, not zero.
- Average return is arithmetic. Variance, standard deviation and covariance use sample estimates
  (`ddof=1`). Annualization factors are conventionally 252, 52 and 12 for daily, weekly and monthly
  observations; exchange-specific holiday calendars are not modeled.
- The annual risk-free input becomes periodic target `(1 + annual rate)^(1 / periods) - 1`.
  Sharpe = annualized mean excess return / annualized standard deviation. Sortino divides the
  same excess return by root-mean-square shortfall below that periodic target, annualized.
  The simulated opportunity set uses the same risk-free conversion.
- Drawdown includes initial capital as a starting high-water mark. Historical VaR is the positive
  loss magnitude at the observed fifth return percentile. Zero volatility makes ratios unavailable.
- Weights are explicit nonnegative capital proportions, normalized to 100%. The periodic basket
  models a constant-weight portfolio; it is distinct from the actual buy-and-hold holdings summary.
  Missing common dates and unequal history spans can limit representativeness. These are historical
  estimates, not predicted investment outcomes.

## Valuation screening

- Cost of equity = risk-free rate + reviewed beta × equity risk premium.
  WACC uses market-equity and interest-bearing-debt capital weights, with after-tax debt cost.
- FCFF is a reviewed input. The UI suggests OCF - capex + after-tax interest, conditional on
  interest being included in OCF; source classification and adjustments require review.
- Enterprise DCF value = discounted explicit FCFF + discounted perpetuity terminal value.
  Terminal value = final FCFF × (1 + terminal growth) / (WACC - terminal growth).
  WACC must exceed terminal growth; impossible sensitivity cells stay unavailable.
  Equity value = enterprise value + cash - debt; value/share uses reviewed shares outstanding.
- Invested capital = interest-bearing debt + equity - cash. ROIC uses NOPAT / average invested
  capital, with ending capital as first-year fallback. NOPAT = EBIT × (1 - tax rate).
  Noncash operating working capital = current assets - cash - current liabilities + short-term debt.
  Reinvestment = capex - depreciation + change in operating working capital.
  Reinvestment rate = reinvestment / positive NOPAT; intrinsic growth = ROIC × reinvestment rate.
  Missing inputs remain unavailable.

## CredGrid pilot cash-flow model

Model `CG-CF-1.2` uses the full calendar-month span of supplied transactions. Internal months with
no rows withhold the score and proposed amount until complete coverage is reviewed. It separates
reviewed financing, owner, personal and transfer receipts from counted business inflows. Other counted
receipt categories are explicitly unverified revenue. Missing balance evidence earns no balance points.

Operating surplus = average counted inflows - reviewed monthly operating expenses. Categorized debt
repayments are excluded from operating expenses. Effective debt service = max(declared monthly debt
service, observed average debt repayments). Maximum new payment = max(operating surplus / minimum
DSCR - effective debt service, 0). Loan capacity discounts the payment annuity at annual proposed
rate / 12. Modeled amount = min(request, capacity), subject to evidence withholding. Proposed annual
rate sums the reviewed risk-free rate and operating, liquidity and credit premiums; at least one
premium must be positive. This pilot score is not calibrated to repayment defaults.
