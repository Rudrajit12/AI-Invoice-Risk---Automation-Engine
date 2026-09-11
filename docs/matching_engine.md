# Stage 4 — Invoice matching engine

The engine produces one outcome per invoice line and never uses synthetic labels to decide that outcome.

| Control | Match type | Action on failure |
| --- | --- | --- |
| Vendor is in master data | 2-way | Hold |
| PO line exists and belongs to referenced PO | 2-way | Hold |
| Invoice vendor, item, and currency agree with PO | 2-way | Hold for vendor; review otherwise |
| Unit price is within 1% of PO price | 2-way | Review |
| Invoiced quantity does not exceed ordered quantity | 2-way | Review |
| Invoiced quantity does not exceed cumulative receipts | 3-way | Review |

Results are written to `outputs/invoice_match_ledger.csv`. `flags` is pipe-delimited so downstream routing and explanations can list every specific issue. `hard_hold` identifies failures that must block payment even before a later risk score is calculated.

The current tolerance configuration is intentionally explicit and local to `MatchConfig`; later calibration can replace the initial 1% price and 0% quantity tolerances without changing rule logic.
