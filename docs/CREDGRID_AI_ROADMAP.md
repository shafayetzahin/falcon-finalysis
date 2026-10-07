# CredGrid AI — pilot boundary and roadmap

CredGrid AI is implemented as a separate, consent-based underwriting decision-support pilot for
small businesses and online shops that are poorly served by conventional small-ticket lending.
It is not mixed into the Falcon Finalysis company score and is never presented as an automatic loan-approval system.

## Implemented pilot

- Consent-gated CSV, XLSX and text-based PDF transaction intake with a reviewable signed ledger.
- Six disclosed scorecard components, evidence confidence, score withholding and reason codes.
- DSCR-constrained loan capacity and benchmark-plus-premium pricing.
- Mandatory benchmark source and as-of date; no silently assumed Bangladesh rate.
- Local saved cases, reviewer HTML report and human Approve/Modify/Decline audit entries.
- Fictional demonstration case and automated formula, parser, storage and UI tests.
- Model `CG-CF-1.2` preserves the full calendar-month span and withholds the score/proposal
  when internal months have no statement transactions. Missing balance evidence earns no balance points.
- Reviewed financing, owner, transfer and personal inflows are excluded from modeled repayment
  capacity. Unknown counted receipt categories remain explicitly unverified revenue.
- Categorized loan repayments are separated from operating expenses. Capacity uses the greater
  of declared and observed average debt service, counted once.
- Changing consent or inputs removes stale scores, proposals and exports. A saved current case and
  explicit confirmation at form submission are required before recording the human decision.

## Intended workflow

1. The applicant provides explicit consent and uploads business transactions, personal/business bank
   statements, marketplace statements, tax/trade documents and other official evidence.
2. The system extracts transactions and documents into a reviewable ledger with source references.
3. Deterministic checks measure revenue stability, cash-flow coverage, seasonality, returned payments,
   existing obligations, customer concentration and document consistency.
4. A documented credit model produces a score band, confidence/coverage measure and specific reason codes.
5. A loan-capacity model proposes a maximum amount and tenure from verified disposable business cash flow,
   repayment frequency and a conservative debt-service coverage requirement.
6. Pricing uses a current Bangladesh risk-free benchmark selected for the relevant tenor, plus documented
   operating-cost, liquidity and risk premiums. The proposed rate must exceed the selected benchmark and
   remain within all applicable lending, disclosure and consumer-protection requirements.
7. A trained human reviewer approves, changes or declines the proposal and records the reason.

## Product boundaries

- Never infer missing income, identity or repayment history.
- Never use religion, gender, ethnicity, disability, political affiliation or other protected traits.
- Separate business affordability from personal identity verification.
- Provide applicants with clear reason codes and a correction/dispute path.
- Test model performance and error rates across legally permitted fairness dimensions before deployment.
- Encrypt documents, minimize retention, record access and support consent withdrawal.
- Version every model, policy, benchmark rate and decision input so a result can be reproduced.
- Treat transaction categorization and document extraction as assistive; material values require review.

## Delivery phases

1. **Evidence intake:** statement ingestion, transaction normalization, document checks and provenance.
2. **Cash-flow profile:** monthly revenue, volatility, recurring expenses, obligations and seasonality.
3. **Credit policy engine:** eligibility rules, coverage thresholds, reason codes and manual review queue.
4. **Score validation:** back-testing on representative outcomes, calibration, monitoring and overrides.
5. **Loan proposal:** amount, tenure and benchmark-linked pricing with affordability constraints.
6. **Controlled pilot:** limited partner deployment, human decisions, audit logs and outcome monitoring.

Legal, regulatory, privacy, pricing and fair-lending review must be completed for the intended Bangladesh
entity and product structure before CredGrid AI influences real credit decisions.
