"""Validate synthetic AP CSV outputs against key business invariants."""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic"


def read(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def unique(rows: list[dict], key: str) -> None:
    assert len(rows) == len({row[key] for row in rows}), f"duplicate {key}"


def main() -> None:
    vendors, pos, receipts, invoices, payments = [read(name) for name in ["vendors.csv", "purchase_orders.csv", "goods_receipts.csv", "invoices.csv", "payments.csv"]]
    assert [len(x) for x in [vendors, pos, receipts, invoices, payments]] == [500, 5000, 8000, 10000, 10000]
    for rows, key in [(vendors, "vendor_id"), (pos, "po_line_id"), (receipts, "receipt_line_id"), (invoices, "invoice_line_id"), (payments, "payment_id")]: unique(rows, key)
    vendor_ids, po_ids, po_line_ids = {x["vendor_id"] for x in vendors}, {x["po_id"] for x in pos}, {x["po_line_id"] for x in pos}
    exception_types = Counter()
    for row in invoices:
        subtotal, tax, total = map(float, (row["line_subtotal"], row["line_tax"], row["line_total"]))
        assert round(subtotal + tax, 2) == total, f"bad total {row['invoice_id']}"
        assert row["exception"] in {"0", "1"}
        types = set(filter(None, row["exception_types"].split("|")))
        assert bool(types) == (row["exception"] == "1"), f"label mismatch {row['invoice_id']}"
        exception_types.update(types)
        if "invalid_vendor" not in types: assert row["vendor_id"] in vendor_ids
        if "invalid_po" not in types: assert row["po_id"] in po_ids and row["po_line_id"] in po_line_ids
    assert sum(int(row["exception"]) for row in invoices) == 2800
    assert exception_types == Counter({"price_mismatch": 700, "quantity_mismatch": 550, "invalid_po": 250, "invalid_vendor": 150, "tax_inconsistency": 300, "amount_anomaly": 300, "late_invoice": 150, "duplicate": 400})
    assert {row["invoice_id"] for row in payments} == {row["invoice_id"] for row in invoices}
    print(f"Validation passed: {len(invoices):,} invoices; {sum(int(row['exception']) for row in invoices):,} labelled exceptions.")


if __name__ == "__main__":
    main()
