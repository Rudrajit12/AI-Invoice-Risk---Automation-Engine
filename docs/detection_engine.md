# Stage 5 — Duplicate and anomaly detection

The detection layer augments the Stage 4 matching ledger and writes `outputs/invoice_control_ledger.csv`.

| Signal | Method | Routing |
| --- | --- | --- |
| Duplicate candidate | Same vendor and supplier invoice reference within seven invoice days | Review |
| Vendor amount anomaly | Vendor-specific median absolute deviation score ≥ 3.5 and invoice at least 3× the valid PO amount | Review |
| Tax-rate mismatch | Invoice tax rate differs from the valid referenced PO line | Review |
| Timing anomaly | Invoice arrives more than 120 days after its PO date | Review |

The detector never reads synthetic labels to set a flag. It leaves Stage 4 hard holds in place and upgrades a prior pass to review when any Stage 5 signal exists. The output summary compares control outcomes with labels strictly for test coverage.

The duplicate rule only marks the later candidate in a close-time pair. In production, its `duplicate_of_invoice_id` value provides the analyst’s comparison record; no invoice is automatically rejected solely because it is a candidate.
