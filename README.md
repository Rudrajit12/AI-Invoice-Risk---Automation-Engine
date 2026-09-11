# AI Invoice Risk & Automation Engine

An accounts-payable control system that evaluates invoices against vendor, purchase-order, receipt, and payment records, then returns a risk score, a routing decision, and clear reasons.

## Product objective

Predict whether an invoice requires manual intervention (`exception = 1`), rather than trying to label fraud. The system will optimize safe touchless processing—not raw model accuracy.

## Delivery roadmap

1. **Business and data architecture** — current milestone
2. Synthetic AP dataset
3. Exploratory data analysis and business insights
4. Two-way / three-way invoice matching rules
5. Duplicate and anomaly detection
6. Risk model
7. Explanation layer
8. Dashboard and API

## Current data contract

The canonical raw entities are:

- `vendors`: approved suppliers and commercial terms
- `purchase_orders`: agreed line-level quantities and prices
- `goods_receipts`: line-level quantities actually received
- `invoices`: submitted invoice lines and a synthetic ground-truth exception label
- `payments`: payment lifecycle records

See [the data model](docs/data_model.md) and [the executable SQL schema](docs/schema.sql). Stage 2 will generate CSV extracts adhering to this contract.

## Decision policy (initial)

| Risk score | Route |
| --- | --- |
| 0–20 | Auto-approve |
| 21–60 | Human review |
| 61–100 | Hold |

These thresholds are placeholders until we can calibrate them against the cost of a false approval and the cost of manual review.

