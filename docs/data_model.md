# Business and data architecture

## Scope and grain

This is a line-aware AP model. Purchase orders, receipts, and invoices may each contain several rows for the same business document. Their respective identifiers (`po_id`, `receipt_id`, and `invoice_id`) identify a document; `*_line_id` identifies its line. This prevents an incorrect total-only match when quantities or prices differ by item.

```text
vendors (1) ──< purchase_orders (1) ──< goods_receipts
    │                 │
    └──────────────< invoices ──< payments
```

An invoice can reference a PO, but synthetic data deliberately includes non-existent and missing PO references. Those rows must be retained and surfaced as exceptions, not dropped by an inner join.

## Canonical entities

### Vendors — one row per supplier

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| vendor_id | string | yes | Stable internal supplier key, e.g. `V0001` |
| vendor_name | string | yes | Approved master-data name |
| category | string | yes | Spend category |
| vendor_since | date | yes | Vendor onboarding date |
| payment_terms_days | integer | yes | Contractual days to pay; positive |
| status | enum | yes | `Active`, `Inactive`, or `Blocked` |

### Purchase orders — one row per PO line

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| po_id / po_line_id | string | yes | PO document and unique line identifiers |
| vendor_id | string | yes | Contracted supplier |
| po_date | date | yes | Date issued |
| item_id | string | yes | Ordered item/service |
| ordered_quantity | decimal | yes | Must be positive |
| unit_price | decimal | yes | Pre-tax unit price; non-negative |
| tax_rate | decimal | yes | Fraction from 0 to 1 |
| currency | string | yes | ISO-style code; initial data is `INR` |

### Goods receipts — one row per receipt line

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| receipt_id / receipt_line_id | string | yes | Receipt document and unique line identifiers |
| po_id / po_line_id | string | yes | Referenced PO line |
| receipt_date | date | yes | Date goods/services were recorded as received |
| item_id | string | yes | Item received; must agree with matched PO |
| quantity_received | decimal | yes | Positive receipt quantity |

### Invoices — one row per invoice line

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| invoice_id / invoice_line_id | string | yes | Vendor document number and unique line identifiers |
| vendor_invoice_reference | string | yes | Supplier-submitted invoice number, retained for duplicate controls |
| vendor_id | string | yes | Submitted vendor key; may be invalid in scenarios |
| vendor_name_raw | string | no | Raw submitted name; can contain harmless variations |
| po_id / po_line_id | string | no | Referenced PO line; may be missing or invalid |
| invoice_date / received_date | date | yes | Issued and AP receipt dates |
| item_id | string | yes | Billed item or service |
| invoice_quantity / unit_price | decimal | yes | Billed quantity and pre-tax unit price |
| tax_rate | decimal | yes | Charged tax fraction |
| line_subtotal / line_tax / line_total | decimal | yes | Calculated monetary values, rounded to two decimals |
| currency | string | yes | Invoice currency |
| source_system | string | yes | E.g. portal, email, EDI |
| exception | boolean | yes | Synthetic ground-truth target at invoice-document level |
| exception_types | string | no | Pipe-delimited injected causes, never used as a predictor |

`exception` and `exception_types` are labels for evaluation. Production inference must derive risk from the raw operational fields only.

### Payments — one row per payment event

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| payment_id | string | yes | Payment-event key |
| invoice_id | string | yes | Invoice document reference |
| payment_date | date | no | Null until paid |
| payment_amount | decimal | no | Amount paid in transaction |
| status | enum | yes | `Scheduled`, `Paid`, `Failed`, `Voided` |

## Document-level derived fields

The generator may emit a document-level invoice summary for EDA, but it should always be reproducible by aggregating invoice lines:

`invoice_subtotal = sum(line_subtotal)`

`invoice_tax = sum(line_tax)`

`invoice_total = sum(line_total)`

## Invariants and validation rules

1. Every canonical ID is non-empty and unique at its declared grain.
2. Dates follow causal order for valid references: `po_date ≤ receipt_date`, and normally `po_date ≤ invoice_date`; scenario exceptions are explicitly labelled.
3. Monetary values use two decimal places and satisfy `line_total = round(line_subtotal + line_tax, 2)`.
4. For non-exception invoice rows referencing valid PO lines, vendor, item, currency, price, and quantity must agree within configured tolerance.
5. A receipt’s cumulative quantity cannot exceed the PO quantity unless it is an intentional over-receipt scenario.
6. Payments aggregate to the invoice total for ordinary paid invoices; partial, duplicate, and failed payments are retained as labelled scenarios.
7. Foreign-key violations are allowed only in `invoices.vendor_id` and `invoices.po_id` when deliberately injecting an exception.

## Initial risk-routing policy

| Score | Decision | Operational meaning |
| ---: | --- | --- |
| 0–20 | `AUTO_APPROVE` | Post without human touch when all hard controls pass |
| 21–60 | `HUMAN_REVIEW` | Queue for AP analyst investigation |
| 61–100 | `HOLD` | Block payment until resolved |

Hard controls (invalid vendor, invalid PO, certain duplicate matches) will later override a low model score.

## Stage 2 synthetic-data design

The next stage will create 500 vendors, roughly 5,000 PO documents, 8,000 receipt events, 10,000 invoice documents, and associated payments. It will allocate normal and exceptional documents intentionally across: invalid vendor/PO, price mismatch, received-quantity mismatch, tax inconsistency, duplicates, late timing, outlier amount, and payment anomalies. Scenario proportions and random seed will be documented for reproducibility.
