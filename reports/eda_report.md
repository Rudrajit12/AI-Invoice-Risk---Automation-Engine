# Stage 3 — Exploratory data analysis

## Dataset scope

This analysis uses synthetic data generated with seed `20260911`: 10,000 invoices, 5,000 PO lines, 8,000 receipt events, and 10,000 payment events.

## Executive findings

1. **28.0% of invoices (2,800) require intervention by design.** This enriched rate is not a production-rate forecast.
2. **Exception-linked invoice value is ₹4,261,496,534 of ₹11,070,863,198 submitted value.** Safety controls should precede touchless-processing optimization.
3. **`amount_anomaly` has the most represented invoice value (₹1,771,578,868).** Its rule should display mismatch and value clearly to AP reviewers.
4. **`Manufacturing` has the highest observed exception rate (30.1%).** This reflects synthetic assignment, not evidence that a real category is riskier.
5. **84.5% of payment events are paid.** Scheduled payments are retained for much of the exception population, connecting risk controls to payment operations.

## Recommendation for Stage 4

Implement separate explainable controls for PO existence, vendor match, price tolerance, received-quantity tolerance, and duplicate candidates (vendor, PO, amount, close invoice date). A blocking control must override a low later model score.

## Limitations

- Scenario labels are injected, not historical AP outcomes.
- This iteration has one invoice line per document; later tests must cover multi-line invoices and partial receipts.
- `exception_types` is evaluation ground truth and must never be used as a predictive feature.
- Invalid-vendor rows intentionally appear as `Unknown / invalid vendor` after joining master data.
