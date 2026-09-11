"""Focused regression checks for matching rules and end-to-end output."""
from __future__ import annotations

import csv
from pathlib import Path

from matching_engine import MatchConfig, evaluate_invoice

ROOT = Path(__file__).resolve().parents[1]


def invoice(**overrides: object) -> dict:
    base = {"invoice_id":"INV-TEST", "invoice_line_id":"INVL-TEST", "vendor_id":"V001", "po_id":"PO001", "po_line_id":"POL001", "item_id":"ITEM-001", "currency":"INR", "unit_price":"100", "invoice_quantity":"10", "line_total":"118", "exception":"0", "exception_types":""}
    return {**base, **overrides}


def main() -> None:
    po = {"POL001": {"po_id":"PO001", "vendor_id":"V001", "item_id":"ITEM-001", "currency":"INR", "unit_price":"100", "ordered_quantity":"10"}}
    common = {"vendors":{"V001"}, "po_lines":po, "receipts":{"POL001":10.0}, "config":MatchConfig()}
    assert evaluate_invoice(invoice(), **common)["match_status"] == "PASS"
    assert "PRICE_MISMATCH" in evaluate_invoice(invoice(unit_price="103"), **common)["flags"]
    assert "RECEIPT_QUANTITY_MISMATCH" in evaluate_invoice(invoice(invoice_quantity="12"), **common)["flags"]
    assert evaluate_invoice(invoice(po_id="PO999"), **common)["match_status"] == "HOLD"
    assert evaluate_invoice(invoice(vendor_id="V999"), **common)["match_status"] == "HOLD"
    ledger = ROOT / "outputs" / "invoice_match_ledger.csv"
    assert ledger.exists(), "Run matching_engine.py before this validator."
    with ledger.open(encoding="utf-8", newline="") as handle: rows = list(csv.DictReader(handle))
    assert len(rows) == 10_000
    assert {row["match_status"] for row in rows} <= {"PASS", "REVIEW", "HOLD"}
    assert {status: sum(row["match_status"] == status for row in rows) for status in ["PASS", "REVIEW", "HOLD"]} == {"PASS": 8050, "REVIEW": 1550, "HOLD": 400}
    print("Matching-engine validation passed.")


if __name__ == "__main__":
    main()
