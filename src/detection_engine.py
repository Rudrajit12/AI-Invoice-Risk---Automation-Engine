"""Stage 5 duplicate and anomaly controls layered onto the match ledger.

Run matching_engine.py first, then run this module. All detections are derived
from operational fields; synthetic labels are used only in the summary.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, OUTPUT = ROOT / "data" / "synthetic", ROOT / "outputs"


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def robust_score(value: float, values: list[float]) -> float:
    """MAD-based score; stable for a vendor's skewed invoice distribution."""
    median = statistics.median(values)
    mad = statistics.median([abs(item - median) for item in values])
    if mad == 0:
        return 0.0 if value == median else float("inf")
    return 0.6745 * (value - median) / mad


def add_duplicate_flags(rows: list[dict], days: int = 7) -> None:
    groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for row in rows:
        key = (row["vendor_id"], row["vendor_invoice_reference"])
        groups[key].append(row)
    for group in groups.values():
        group.sort(key=lambda row: (row["invoice_date"], row["invoice_id"]))
        seen: list[dict] = []
        for row in group:
            current = date.fromisoformat(row["invoice_date"])
            match = next((prior for prior in reversed(seen) if (current - date.fromisoformat(prior["invoice_date"])).days <= days), None)
            if match:
                row["duplicate_candidate"] = True
                row["duplicate_of_invoice_id"] = match["invoice_id"]
            seen.append(row)


def add_anomaly_flags(rows: list[dict]) -> None:
    values_by_vendor: dict[str, list[float]] = defaultdict(list)
    for row in rows: values_by_vendor[row["vendor_id"]].append(float(row["line_total"]))
    for row in rows:
        values = values_by_vendor[row["vendor_id"]]
        score = robust_score(float(row["line_total"]), values) if len(values) >= 8 else 0.0
        row["vendor_amount_robust_z"] = round(score, 4) if score != float("inf") else "inf"
        row["amount_anomaly"] = score >= 3.5 and float(row["po_amount_ratio"] or 0) >= 3.0


def main() -> None:
    ledger = read(OUTPUT / "invoice_match_ledger.csv")
    invoices = {row["invoice_line_id"]: row for row in read(DATA / "invoices.csv")}
    po_lines = {row["po_line_id"]: row for row in read(DATA / "purchase_orders.csv")}
    rows = []
    for match in ledger:
        raw = invoices[match["invoice_line_id"]]
        row = {**match, "invoice_date": raw["invoice_date"], "vendor_invoice_reference": raw["vendor_invoice_reference"], "item_id": raw["item_id"], "invoice_quantity": raw["invoice_quantity"], "unit_price": raw["unit_price"], "tax_rate": raw["tax_rate"], "line_total": raw["line_total"], "po_amount_ratio": "", "duplicate_candidate": False, "duplicate_of_invoice_id": "", "amount_anomaly": False, "vendor_amount_robust_z": "", "tax_rate_match": "", "timing_anomaly": False}
        po = po_lines.get(raw["po_line_id"])
        if po and po["po_id"] == raw["po_id"]:
            po_total = float(po["ordered_quantity"]) * float(po["unit_price"]) * (1 + float(po["tax_rate"]))
            row["po_amount_ratio"] = round(float(raw["line_total"]) / po_total, 6) if po_total else ""
            row["tax_rate_match"] = abs(float(raw["tax_rate"]) - float(po["tax_rate"])) < 0.000001
            row["timing_anomaly"] = (date.fromisoformat(raw["invoice_date"]) - date.fromisoformat(po["po_date"])).days > 120
        rows.append(row)
    add_duplicate_flags(rows)
    add_anomaly_flags(rows)
    for row in rows:
        flags = list(filter(None, row["flags"].split("|")))
        if row["duplicate_candidate"]: flags.append("DUPLICATE_CANDIDATE")
        if row["amount_anomaly"]: flags.append("VENDOR_AMOUNT_ANOMALY")
        if row["tax_rate_match"] is False: flags.append("TAX_RATE_MISMATCH")
        if row["timing_anomaly"]: flags.append("TIMING_ANOMALY")
        row["flags"] = "|".join(flags)
        row["control_status"] = "HOLD" if row["hard_hold"] == "True" else ("REVIEW" if flags else "PASS")
    fields = list(rows[0])
    with (OUTPUT / "invoice_control_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    status_counts = {status: sum(row["control_status"] == status for row in rows) for status in ["PASS", "REVIEW", "HOLD"]}
    labelled = sum(row["synthetic_exception"] == "1" for row in rows)
    detected = sum(row["control_status"] != "PASS" and row["synthetic_exception"] == "1" for row in rows)
    false_alerts = sum(row["control_status"] != "PASS" and row["synthetic_exception"] == "0" for row in rows)
    flags = {flag: sum(flag in row["flags"].split("|") for row in rows) for flag in ["DUPLICATE_CANDIDATE", "VENDOR_AMOUNT_ANOMALY", "TAX_RATE_MISMATCH", "TIMING_ANOMALY"]}
    summary = {"control_status_counts": status_counts, "labelled_exceptions": labelled, "exceptions_captured": detected, "exception_recall": round(detected / labelled, 4), "false_alerts_against_synthetic_labels": false_alerts, "new_signal_counts": flags}
    (OUTPUT / "detection_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Detection complete: PASS={status_counts['PASS']:,}, REVIEW={status_counts['REVIEW']:,}, HOLD={status_counts['HOLD']:,}; recall={summary['exception_recall']:.1%}.")


if __name__ == "__main__":
    main()
