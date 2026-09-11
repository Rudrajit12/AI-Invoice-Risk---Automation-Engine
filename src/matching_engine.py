"""Explainable two-way and three-way invoice matching rules.

Run:
    python src/matching_engine.py

The resulting ledger contains only operational inputs and rule outcomes. The
synthetic `exception` fields are retained only for evaluation, never used to
make a matching decision.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic"
OUTPUT = ROOT / "outputs"


@dataclass(frozen=True)
class MatchConfig:
    price_tolerance_pct: float = 0.01
    quantity_tolerance_pct: float = 0.00
    require_receipt: bool = True


def read(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(row: dict, field: str) -> float:
    return float(row[field])


def ratio_difference(actual: float, expected: float) -> float:
    return abs(actual - expected) / expected if expected else (0.0 if actual == 0 else float("inf"))


def evaluate_invoice(invoice: dict, *, vendors: set[str], po_lines: dict[str, dict], receipts: dict[str, float], config: MatchConfig) -> dict:
    flags: list[str] = []
    vendor_valid = invoice["vendor_id"] in vendors
    po = po_lines.get(invoice["po_line_id"])
    po_valid = po is not None and po["po_id"] == invoice["po_id"]
    if not vendor_valid: flags.append("INVALID_VENDOR")
    if not po_valid: flags.append("INVALID_PO")
    result = {
        "invoice_id": invoice["invoice_id"], "invoice_line_id": invoice["invoice_line_id"],
        "vendor_id": invoice["vendor_id"], "po_id": invoice["po_id"], "po_line_id": invoice["po_line_id"],
        "invoice_total": number(invoice, "line_total"), "vendor_valid": vendor_valid, "po_valid": po_valid,
        "vendor_match": False, "item_match": False, "currency_match": False, "price_match": False,
        "quantity_match": False, "receipt_match": False, "po_unit_price": "", "received_quantity": "",
        "price_variance_pct": "", "receipt_quantity_variance_pct": "", "flags": "", "match_status": "",
        "hard_hold": False, "synthetic_exception": invoice["exception"], "synthetic_exception_types": invoice["exception_types"],
    }
    if po_valid:
        result["vendor_match"] = invoice["vendor_id"] == po["vendor_id"]
        result["item_match"] = invoice["item_id"] == po["item_id"]
        result["currency_match"] = invoice["currency"] == po["currency"]
        price_variance = ratio_difference(number(invoice, "unit_price"), number(po, "unit_price"))
        received = receipts.get(invoice["po_line_id"], 0.0)
        receipt_variance = ratio_difference(number(invoice, "invoice_quantity"), received)
        result.update({"po_unit_price": number(po, "unit_price"), "received_quantity": round(received, 2), "price_variance_pct": round(price_variance, 6), "receipt_quantity_variance_pct": round(receipt_variance, 6), "price_match": price_variance <= config.price_tolerance_pct, "quantity_match": number(invoice, "invoice_quantity") <= number(po, "ordered_quantity") * (1 + config.quantity_tolerance_pct), "receipt_match": number(invoice, "invoice_quantity") <= received * (1 + config.quantity_tolerance_pct)})
        if not result["vendor_match"]: flags.append("VENDOR_PO_MISMATCH")
        if not result["item_match"]: flags.append("ITEM_MISMATCH")
        if not result["currency_match"]: flags.append("CURRENCY_MISMATCH")
        if not result["price_match"]: flags.append("PRICE_MISMATCH")
        if not result["quantity_match"]: flags.append("PO_QUANTITY_MISMATCH")
        if config.require_receipt and not result["receipt_match"]: flags.append("RECEIPT_QUANTITY_MISMATCH")
    result["hard_hold"] = any(flag in {"INVALID_VENDOR", "INVALID_PO", "VENDOR_PO_MISMATCH"} for flag in flags)
    result["flags"] = "|".join(flags)
    result["match_status"] = "PASS" if not flags else ("HOLD" if result["hard_hold"] else "REVIEW")
    return result


def main() -> None:
    config = MatchConfig()
    vendors = {row["vendor_id"] for row in read("vendors.csv")}
    po_lines = {row["po_line_id"]: row for row in read("purchase_orders.csv")}
    receipts: dict[str, float] = defaultdict(float)
    for row in read("goods_receipts.csv"): receipts[row["po_line_id"]] += number(row, "quantity_received")
    results = [evaluate_invoice(row, vendors=vendors, po_lines=po_lines, receipts=receipts, config=config) for row in read("invoices.csv")]
    OUTPUT.mkdir(exist_ok=True)
    fields = list(results[0])
    with (OUTPUT / "invoice_match_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(results)
    counts = defaultdict(int)
    for row in results: counts[row["match_status"]] += 1
    detected = sum(row["match_status"] != "PASS" and row["synthetic_exception"] == "1" for row in results)
    false_alerts = sum(row["match_status"] != "PASS" and row["synthetic_exception"] == "0" for row in results)
    labelled_exceptions = sum(row["synthetic_exception"] == "1" for row in results)
    summary = {"match_status_counts": dict(counts), "labelled_exceptions": labelled_exceptions, "exceptions_captured_by_matching": detected, "matching_exception_recall": round(detected / labelled_exceptions, 4), "false_alerts_against_synthetic_labels": false_alerts, "out_of_scope_for_matching": ["duplicate", "tax_inconsistency", "late_invoice"]}
    (OUTPUT / "matching_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Matching complete: PASS={counts['PASS']:,}, REVIEW={counts['REVIEW']:,}, HOLD={counts['HOLD']:,}.")


if __name__ == "__main__":
    main()
