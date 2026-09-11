"""Generate a reproducible, scenario-driven synthetic AP dataset.

Run from the repository root:
    python src/generate_synthetic_data.py

The output represents document lines; this first dataset intentionally uses one
line per document, while retaining line identifiers for later multi-line data.
"""
from __future__ import annotations

import csv
import json
import random
import shutil
from collections import Counter
from datetime import date, timedelta
from pathlib import Path


SEED = 20260911
VENDOR_COUNT = 500
PO_COUNT = 5_000
RECEIPT_COUNT = 8_000
INVOICE_COUNT = 10_000
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "synthetic"

CATEGORIES = {
    "Manufacturing": (80, 3_500),
    "Logistics": (500, 12_000),
    "IT Services": (1_500, 25_000),
    "Office Supplies": (50, 2_000),
    "Facilities": (300, 8_000),
    "Professional Services": (2_000, 40_000),
    "Marketing": (700, 18_000),
    "Utilities": (200, 5_000),
}
PREFIXES = ["Apex", "Bluewave", "Crest", "Delta", "Evergreen", "Fusion", "Global", "Horizon", "Indus", "Jupiter"]
SUFFIXES = ["Components", "Logistics", "Solutions", "Enterprises", "Industries", "Services", "Supplies", "Systems"]
SOURCE_SYSTEMS = ["Vendor Portal", "EDI", "Email OCR", "Supplier Network"]


def iso(day: date) -> str:
    return day.isoformat()


def money(value: float) -> float:
    return round(value, 2)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def weighted_vendor(rng: random.Random, vendors: list[dict]) -> dict:
    # Established vendors have more activity, creating useful history for EDA.
    return rng.choices(vendors, weights=[v["activity_weight"] for v in vendors], k=1)[0]


def make_vendors(rng: random.Random) -> list[dict]:
    start = date(2018, 1, 1)
    end = date(2025, 12, 31)
    categories = list(CATEGORIES)
    rows = []
    for i in range(1, VENDOR_COUNT + 1):
        since = start + timedelta(days=rng.randint(0, (end - start).days))
        category = rng.choice(categories)
        rows.append({
            "vendor_id": f"V{i:04d}",
            "vendor_name": f"{rng.choice(PREFIXES)} {rng.choice(SUFFIXES)} Pvt Ltd",
            "category": category,
            "vendor_since": iso(since),
            "payment_terms_days": rng.choice([15, 30, 30, 30, 45, 60]),
            "status": "Active" if rng.random() < 0.95 else rng.choice(["Inactive", "Blocked"]),
            "activity_weight": rng.randint(1, 12),
        })
    return rows


def make_purchase_orders(rng: random.Random, vendors: list[dict]) -> list[dict]:
    rows = []
    for i in range(1, PO_COUNT + 1):
        vendor = weighted_vendor(rng, vendors)
        category = vendor["category"]
        low, high = CATEGORIES[category]
        po_day = date(2026, 1, 1) + timedelta(days=rng.randint(0, 210))
        quantity = rng.choice([1, 2, 5, 10, 20, 50, 100, 250, 500])
        unit_price = money(rng.uniform(low, high))
        rows.append({
            "po_id": f"PO{i:05d}",
            "po_line_id": f"POL{i:06d}",
            "vendor_id": vendor["vendor_id"],
            "po_date": iso(po_day),
            "item_id": f"{category[:3].upper()}-{rng.randint(1, 160):03d}",
            "ordered_quantity": quantity,
            "unit_price": unit_price,
            "tax_rate": rng.choice([0.0, 0.05, 0.12, 0.18]),
            "currency": "INR",
        })
    return rows


def make_receipts(rng: random.Random, pos: list[dict]) -> list[dict]:
    rows = []
    # Every PO has a baseline full receipt. This makes normal three-way matches
    # genuinely pass; the remaining events emulate split/late receiving activity.
    receipt_pos = list(pos) + [rng.choice(pos) for _ in range(RECEIPT_COUNT - len(pos))]
    for i, po in enumerate(receipt_pos, 1):
        po_day = date.fromisoformat(po["po_date"])
        received = po["ordered_quantity"] if i <= len(pos) else po["ordered_quantity"] * rng.choice([0.25, 0.5, 0.75])
        # A small labelled over-receipt set is intentional.
        if i <= 80:
            received = po["ordered_quantity"] * rng.uniform(1.05, 1.25)
        rows.append({
            "receipt_id": f"GR{i:05d}",
            "receipt_line_id": f"GRL{i:06d}",
            "po_id": po["po_id"],
            "po_line_id": po["po_line_id"],
            "receipt_date": iso(po_day + timedelta(days=rng.randint(1, 55))),
            "item_id": po["item_id"],
            "quantity_received": money(received),
        })
    return rows


def raw_name(rng: random.Random, name: str) -> str:
    roll = rng.random()
    if roll < 0.06:
        return name.upper()
    if roll < 0.12:
        return name.replace(" Pvt Ltd", "")
    if roll < 0.16:
        return name.replace(" ", "  ")
    return name


def add_invoice(rows: list[dict], *, invoice_id: str, vendor: dict, po: dict | None,
                invoice_day: date, quantity: float, unit_price: float, tax_rate: float,
                exception_types: list[str], rng: random.Random, po_id: str | None = None,
                po_line_id: str | None = None, item_id: str | None = None,
                vendor_invoice_reference: str | None = None) -> None:
    subtotal = money(quantity * unit_price)
    tax = money(subtotal * tax_rate)
    rows.append({
        "invoice_id": invoice_id,
        "invoice_line_id": f"INVL{len(rows) + 1:06d}",
        "vendor_invoice_reference": vendor_invoice_reference or f"SUP-{invoice_id}",
        "vendor_id": vendor["vendor_id"],
        "vendor_name_raw": raw_name(rng, vendor["vendor_name"]),
        "po_id": po_id if po_id is not None else (po["po_id"] if po else ""),
        "po_line_id": po_line_id if po_line_id is not None else (po["po_line_id"] if po else ""),
        "invoice_date": iso(invoice_day),
        "received_date": iso(invoice_day + timedelta(days=rng.randint(0, 8))),
        "item_id": item_id if item_id is not None else (po["item_id"] if po else "UNCLASSIFIED-001"),
        "invoice_quantity": money(quantity),
        "unit_price": money(unit_price),
        "tax_rate": tax_rate,
        "line_subtotal": subtotal,
        "line_tax": tax,
        "line_total": money(subtotal + tax),
        "currency": "INR",
        "source_system": rng.choice(SOURCE_SYSTEMS),
        "exception": int(bool(exception_types)),
        "exception_types": "|".join(exception_types),
    })


def make_invoices(rng: random.Random, vendors: list[dict], pos: list[dict], receipts: list[dict]) -> list[dict]:
    rows: list[dict] = []
    receipts_by_line: dict[str, float] = Counter()
    for receipt in receipts:
        receipts_by_line[receipt["po_line_id"]] += receipt["quantity_received"]
    active = [v for v in vendors if v["status"] == "Active"]
    scenario_counts = {
        "normal": 7_200, "price_mismatch": 700, "quantity_mismatch": 550,
        "invalid_po": 250, "invalid_vendor": 150, "tax_inconsistency": 300,
        "amount_anomaly": 300, "late_invoice": 150, "duplicate": 400,
    }
    for i in range(1, scenario_counts["normal"] + 1):
        po = rng.choice(pos); vendor = next(v for v in vendors if v["vendor_id"] == po["vendor_id"])
        po_day = date.fromisoformat(po["po_date"])
        add_invoice(rows, invoice_id=f"INV{i:05d}", vendor=vendor, po=po,
                    invoice_day=po_day + timedelta(days=rng.randint(2, 75)),
                    quantity=po["ordered_quantity"], unit_price=po["unit_price"], tax_rate=po["tax_rate"],
                    exception_types=[], rng=rng)
    base = len(rows)
    for idx in range(1, scenario_counts["price_mismatch"] + 1):
        po = rng.choice(pos); vendor = next(v for v in vendors if v["vendor_id"] == po["vendor_id"])
        add_invoice(rows, invoice_id=f"INV{base + idx:05d}", vendor=vendor, po=po,
                    invoice_day=date.fromisoformat(po["po_date"]) + timedelta(days=rng.randint(3, 65)),
                    quantity=po["ordered_quantity"], unit_price=money(po["unit_price"] * rng.uniform(1.05, 1.35)),
                    tax_rate=po["tax_rate"], exception_types=["price_mismatch"], rng=rng)
    base = len(rows)
    for idx in range(1, scenario_counts["quantity_mismatch"] + 1):
        po = rng.choice(pos); vendor = next(v for v in vendors if v["vendor_id"] == po["vendor_id"])
        received = receipts_by_line.get(po["po_line_id"], 0)
        billed = max(po["ordered_quantity"], received) * rng.uniform(1.08, 1.35)
        add_invoice(rows, invoice_id=f"INV{base + idx:05d}", vendor=vendor, po=po,
                    invoice_day=date.fromisoformat(po["po_date"]) + timedelta(days=rng.randint(4, 70)),
                    quantity=money(billed), unit_price=po["unit_price"], tax_rate=po["tax_rate"],
                    exception_types=["quantity_mismatch"], rng=rng)
    base = len(rows)
    for idx in range(1, scenario_counts["invalid_po"] + scenario_counts["invalid_vendor"] + 1):
        vendor = rng.choice(active); po_day = date(2026, 7, 1) + timedelta(days=rng.randint(0, 60))
        invalid_vendor = idx > scenario_counts["invalid_po"]
        if invalid_vendor:
            po = rng.choice(pos)
            submitted = dict(vendor); submitted["vendor_id"] = f"VX{idx:04d}"; submitted["vendor_name"] = f"Unverified Vendor {idx}"
            add_invoice(rows, invoice_id=f"INV{base + idx:05d}", vendor=submitted, po=po, invoice_day=po_day,
                        quantity=po["ordered_quantity"], unit_price=po["unit_price"], tax_rate=po["tax_rate"],
                        exception_types=["invalid_vendor"], rng=rng)
        else:
            add_invoice(rows, invoice_id=f"INV{base + idx:05d}", vendor=vendor, po=None, invoice_day=po_day,
                        quantity=rng.choice([1, 5, 10, 20]), unit_price=money(rng.uniform(500, 10_000)), tax_rate=0.18,
                        exception_types=["invalid_po"], rng=rng,
                        po_id=f"POX{idx:05d}", po_line_id=f"POLX{idx:06d}", item_id="UNKNOWN-001")
    base = len(rows)
    for idx in range(1, scenario_counts["tax_inconsistency"] + scenario_counts["amount_anomaly"] + scenario_counts["late_invoice"] + 1):
        po = rng.choice(pos); vendor = next(v for v in vendors if v["vendor_id"] == po["vendor_id"])
        if idx <= scenario_counts["tax_inconsistency"]:
            types, rate, day, qty, price = ["tax_inconsistency"], (0.18 if po["tax_rate"] != 0.18 else 0.05), 20, po["ordered_quantity"], po["unit_price"]
        elif idx <= scenario_counts["tax_inconsistency"] + scenario_counts["amount_anomaly"]:
            types, rate, day, qty, price = ["amount_anomaly"], po["tax_rate"], 35, po["ordered_quantity"], money(po["unit_price"] * rng.uniform(4.0, 8.0))
        else:
            types, rate, day, qty, price = ["late_invoice"], po["tax_rate"], rng.randint(180, 300), po["ordered_quantity"], po["unit_price"]
        add_invoice(rows, invoice_id=f"INV{base + idx:05d}", vendor=vendor, po=po,
                    invoice_day=date.fromisoformat(po["po_date"]) + timedelta(days=day), quantity=qty,
                    unit_price=price, tax_rate=rate, exception_types=types, rng=rng)
    # Duplicates replicate core commercial fields but receive independent invoice IDs.
    candidates = rng.sample(rows[:7_200], scenario_counts["duplicate"])
    base = len(rows)
    for idx, original in enumerate(candidates, 1):
        vendor = next(v for v in vendors if v["vendor_id"] == original["vendor_id"])
        po = next(p for p in pos if p["po_line_id"] == original["po_line_id"])
        add_invoice(rows, invoice_id=f"INV{base + idx:05d}", vendor=vendor, po=po,
                    invoice_day=date.fromisoformat(original["invoice_date"]) + timedelta(days=rng.randint(0, 3)),
                    quantity=original["invoice_quantity"], unit_price=original["unit_price"], tax_rate=original["tax_rate"],
                    exception_types=["duplicate"], rng=rng, vendor_invoice_reference=original["vendor_invoice_reference"])
    assert len(rows) == INVOICE_COUNT
    return rows


def make_payments(rng: random.Random, invoices: list[dict], vendor_terms: dict[str, int]) -> list[dict]:
    rows = []
    for i, invoice in enumerate(invoices, 1):
        inv_day = date.fromisoformat(invoice["invoice_date"])
        if invoice["exception"] and rng.random() < 0.55:
            status, pay_day, amount = "Scheduled", None, None
        else:
            terms = vendor_terms.get(invoice["vendor_id"], 30)
            status, pay_day, amount = "Paid", inv_day + timedelta(days=rng.randint(5, terms + 15)), invoice["line_total"]
        rows.append({"payment_id": f"PAY{i:06d}", "invoice_id": invoice["invoice_id"], "payment_date": iso(pay_day) if pay_day else "", "payment_amount": amount if amount is not None else "", "status": status})
    return rows


def main() -> None:
    rng = random.Random(SEED)
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    vendors = make_vendors(rng)
    pos = make_purchase_orders(rng, vendors)
    receipts = make_receipts(rng, pos)
    invoices = make_invoices(rng, vendors, pos, receipts)
    payments = make_payments(rng, invoices, {v["vendor_id"]: v["payment_terms_days"] for v in vendors})
    write_csv(OUTPUT_DIR / "vendors.csv", [{k: v for k, v in row.items() if k != "activity_weight"} for row in vendors], ["vendor_id", "vendor_name", "category", "vendor_since", "payment_terms_days", "status"])
    write_csv(OUTPUT_DIR / "purchase_orders.csv", pos, list(pos[0]))
    write_csv(OUTPUT_DIR / "goods_receipts.csv", receipts, list(receipts[0]))
    write_csv(OUTPUT_DIR / "invoices.csv", invoices, list(invoices[0]))
    write_csv(OUTPUT_DIR / "payments.csv", payments, list(payments[0]))
    manifest = {"seed": SEED, "counts": {"vendors": len(vendors), "purchase_orders": len(pos), "goods_receipts": len(receipts), "invoices": len(invoices), "payments": len(payments)}, "invoice_scenarios": dict(sorted(Counter("normal" if not row["exception_types"] else row["exception_types"] for row in invoices).items()))}
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
