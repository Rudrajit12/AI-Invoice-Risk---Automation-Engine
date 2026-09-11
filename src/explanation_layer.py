"""Create grounded, human-readable explanations for scored invoice decisions."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, OUTPUT = ROOT / "data" / "synthetic", ROOT / "outputs"


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def inr(value: str | float) -> str:
    return f"₹{float(value):,.2f}"


def percent(value: str | float) -> str:
    return f"{float(value) * 100:.1f}%"


def explain(row: dict, po_lines: dict[str, dict]) -> tuple[str, str]:
    """Return a compact summary and ordered, evidence-only detailed rationale."""
    flags = set(filter(None, row["flags"].split("|")))
    po = po_lines.get(row["po_line_id"])
    reasons: list[str] = []
    if "INVALID_VENDOR" in flags:
        reasons.append(f"Vendor `{row['vendor_id']}` is not present in the approved vendor master.")
    if "INVALID_PO" in flags:
        reasons.append(f"Referenced PO `{row['po_id'] or 'not supplied'}` does not resolve to a valid PO line.")
    if "VENDOR_PO_MISMATCH" in flags:
        reasons.append("The invoice vendor does not match the vendor recorded on the referenced purchase order.")
    if "PRICE_MISMATCH" in flags:
        reasons.append(f"Unit price is {inr(row['unit_price'])} versus PO price {inr(row['po_unit_price'])}, a variance of {percent(row['price_variance_pct'])}.")
    if "PO_QUANTITY_MISMATCH" in flags:
        reasons.append("Billed quantity exceeds the quantity ordered on the referenced PO line.")
    if "RECEIPT_QUANTITY_MISMATCH" in flags:
        reasons.append(f"Billed quantity is {float(row['invoice_quantity']):,.2f}; cumulative recorded receipt quantity is {float(row['received_quantity']):,.2f}.")
    if "DUPLICATE_CANDIDATE" in flags:
        reasons.append(f"Supplier invoice reference `{row['vendor_invoice_reference']}` matches earlier invoice `{row['duplicate_of_invoice_id']}` within seven days.")
    if "VENDOR_AMOUNT_ANOMALY" in flags:
        reasons.append(f"Invoice value is {float(row['po_amount_ratio']):.1f}× the approved PO amount and is unusual for this vendor (robust score {row['vendor_amount_robust_z']}).")
    if "TAX_RATE_MISMATCH" in flags and po:
        reasons.append(f"Invoice tax rate is {percent(row['tax_rate'])}; PO tax rate is {percent(po['tax_rate'])}.")
    if "TIMING_ANOMALY" in flags and po:
        days = (date.fromisoformat(row["invoice_date"]) - date.fromisoformat(po["po_date"])).days
        reasons.append(f"Invoice date is {days:,} days after the PO date, above the 120-day timing threshold.")
    if row["risk_decision"] == "AUTO_APPROVE":
        summary = f"Auto-approve: risk score {row['risk_score']}/100. No configured matching, duplicate, tax, timing, or vendor-amount controls were triggered."
    elif row["risk_decision"] == "HOLD":
        summary = f"Hold: risk score {row['risk_score']}/100. A payment-blocking control requires resolution before payment."
    else:
        summary = f"Human review: risk score {row['risk_score']}/100. Review the evidence below before releasing payment."
    return summary, " ".join(reasons) or "No deterministic exception reason was recorded; review the model score and source documents."


def main() -> None:
    po_lines = {row["po_line_id"]: row for row in read(DATA / "purchase_orders.csv")}
    rows = read(OUTPUT / "invoice_risk_ledger.csv")
    explained = []
    for row in rows:
        summary, rationale = explain(row, po_lines)
        explained.append({"invoice_id": row["invoice_id"], "invoice_line_id": row["invoice_line_id"], "vendor_id": row["vendor_id"], "po_id": row["po_id"], "invoice_total": row["invoice_total"], "risk_score": row["risk_score"], "risk_decision": row["risk_decision"], "flags": row["flags"], "decision_summary": summary, "evidence_rationale": rationale})
    with (OUTPUT / "invoice_explanations.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(explained[0])); writer.writeheader(); writer.writerows(explained)
    print(f"Explanation layer complete: {len(explained):,} grounded explanations written.")


if __name__ == "__main__":
    main()
