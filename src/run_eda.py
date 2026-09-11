"""Create a dependency-free EDA report, summaries, and portable SVG charts."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, REPORTS = ROOT / "data" / "synthetic", ROOT / "reports"
FIGURES = REPORTS / "figures"


def read(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save_csv(name: str, rows: list[dict], fields: list[str]) -> None:
    with (REPORTS / name).open("w", encoding="utf-8", newline="") as f:
        out = csv.DictWriter(f, fieldnames=fields); out.writeheader(); out.writerows(rows)


def pct(value: float) -> str: return f"{value:.1%}"
def money(value: float) -> str: return f"₹{value:,.0f}"
def html(value: object) -> str: return str(value).replace("&", "&amp;").replace("<", "&lt;")


def chart(rows: list[tuple[str, float]], title: str, unit: str, path: Path, percent: bool = False) -> None:
    """Write a simple, no-dependency accessible vertical bar chart."""
    width, height, left, bottom, top = 1050, 560, 100, 160, 80
    plot_w, plot_h, maximum = width-left-25, height-bottom-top, max(v for _, v in rows) or 1
    gap, bar_w = 12, max(20, (plot_w - 12 * (len(rows) + 1)) / len(rows))
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html(title)}">', '<style>text{font-family:Arial,sans-serif;fill:#172033}.g{stroke:#d5dae3}.b{fill:#2563eb}.a{font-size:11px}.v{font-size:11px;font-weight:bold}</style>', f'<text x="{left}" y="32" font-size="20" font-weight="bold">{html(title)}</text>', f'<text x="{left}" y="54" class="a">{html(unit)}</text>']
    for i in range(5):
        y, value = top+plot_h-i*plot_h/4, maximum*i/4
        svg += [f'<line class="g" x1="{left}" y1="{y:.1f}" x2="{width-25}" y2="{y:.1f}"/>', f'<text class="a" x="{left-8}" y="{y+4:.1f}" text-anchor="end">{pct(value) if percent else f"{value:,.0f}"}</text>']
    for i, (label, value) in enumerate(rows):
        x, h = left+gap+i*(bar_w+gap), value/maximum*plot_h
        y = top+plot_h-h
        svg += [f'<rect class="b" x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}"/>', f'<text class="v" x="{x+bar_w/2:.1f}" y="{y-7:.1f}" text-anchor="middle">{pct(value) if percent else f"{value:,.0f}"}</text>', f'<text class="a" x="{x+bar_w/2:.1f}" y="{height-125}" text-anchor="end" transform="rotate(-35 {x+bar_w/2:.1f},{height-125})">{html(label)}</text>']
    path.write_text("\n".join(svg+["</svg>"]), encoding="utf-8")


def main() -> None:
    REPORTS.mkdir(exist_ok=True); FIGURES.mkdir(exist_ok=True)
    invoices, vendors, pos, receipts, payments = [read(x) for x in ["invoices.csv", "vendors.csv", "purchase_orders.csv", "goods_receipts.csv", "payments.csv"]]
    manifest = json.loads((DATA / "manifest.json").read_text())
    masters = {x["vendor_id"]: x for x in vendors}
    categories, scenarios, vendor_data, months = [defaultdict(lambda: {"invoices":0,"exceptions":0,"invoice_value":0.0,"exception_value":0.0}) for _ in range(4)]
    pay_data = defaultdict(lambda: {"events": 0, "payment_value": 0.0})
    total, exceptions = 0.0, 0
    for x in invoices:
        value, flag, category, scenario, month = float(x["line_total"]), int(x["exception"]), masters.get(x["vendor_id"], {"category":"Unknown / invalid vendor"})["category"], x["exception_types"] or "normal", x["invoice_date"][:7]
        total += value; exceptions += flag
        for collection, key in [(categories, category), (scenarios, scenario), (vendor_data, x["vendor_id"]), (months, month)]:
            collection[key]["invoices"] += 1; collection[key]["exceptions"] += flag; collection[key]["invoice_value"] += value; collection[key]["exception_value"] += value*flag
    for x in payments:
        pay_data[x["status"]]["events"] += 1; pay_data[x["status"]]["payment_value"] += float(x["payment_amount"] or 0)
    def summarized(source, name):
        return sorted([{name:k, **v, "exception_rate":v["exceptions"]/v["invoices"]} for k,v in source.items()], key=lambda r:r["exception_rate"], reverse=True)
    cat_rows, scn_rows, mon_rows = summarized(categories,"category"), summarized(scenarios,"exception_type"), sorted(summarized(months,"invoice_month"), key=lambda r:r["invoice_month"])
    vendor_rows = sorted(summarized(vendor_data,"vendor_id"), key=lambda r:(r["exception_value"], r["exception_rate"]), reverse=True)
    payment_rows = [{"status":k, **v} for k,v in sorted(pay_data.items())]
    base_fields = ["invoices","exceptions","exception_rate","invoice_value","exception_value"]
    save_csv("category_summary.csv", cat_rows, ["category", *base_fields]); save_csv("scenario_summary.csv", scn_rows, ["exception_type", *base_fields]); save_csv("top_vendor_exposure.csv", vendor_rows[:20], ["vendor_id", *base_fields]); save_csv("monthly_summary.csv", mon_rows, ["invoice_month", *base_fields]); save_csv("payment_summary.csv", payment_rows, ["status","events","payment_value"])
    chart([(x["category"],x["exception_rate"]) for x in cat_rows], "Exception rate by vendor category", "Exception rate", FIGURES / "exception_rate_by_category.svg", True)
    chart([(x["exception_type"],x["invoice_value"]) for x in sorted(scn_rows,key=lambda r:r["invoice_value"],reverse=True)], "Invoice value by scenario", "Total invoice value (INR)", FIGURES / "invoice_value_by_scenario.svg")
    chart([(x["invoice_month"],x["exception_rate"]) for x in mon_rows], "Monthly exception rate", "Exception rate", FIGURES / "monthly_exception_rate.svg", True)
    exception_value = sum(x["exception_value"] for x in scn_rows)
    top_scenario = max((x for x in scn_rows if x["exception_type"] != "normal"), key=lambda x:x["invoice_value"])
    top_category = next(x for x in cat_rows if x["category"] != "Unknown / invalid vendor")
    paid_rate=pay_data["Paid"]["events"]/len(payments)
    report = f"""# Stage 3 — Exploratory data analysis

## Dataset scope

This analysis uses synthetic data generated with seed `{manifest['seed']}`: {len(invoices):,} invoices, {len(pos):,} PO lines, {len(receipts):,} receipt events, and {len(payments):,} payment events.

## Executive findings

1. **{pct(exceptions/len(invoices))} of invoices ({exceptions:,}) require intervention by design.** This enriched rate is not a production-rate forecast.
2. **Exception-linked invoice value is {money(exception_value)} of {money(total)} submitted value.** Safety controls should precede touchless-processing optimization.
3. **`{top_scenario['exception_type']}` has the most represented invoice value ({money(top_scenario['invoice_value'])}).** Its rule should display mismatch and value clearly to AP reviewers.
4. **`{top_category['category']}` has the highest observed exception rate ({pct(top_category['exception_rate'])}).** This reflects synthetic assignment, not evidence that a real category is riskier.
5. **{pct(paid_rate)} of payment events are paid.** Scheduled payments are retained for much of the exception population, connecting risk controls to payment operations.

## Recommendation for Stage 4

Implement separate explainable controls for PO existence, vendor match, price tolerance, received-quantity tolerance, and duplicate candidates (vendor, PO, amount, close invoice date). A blocking control must override a low later model score.

## Limitations

- Scenario labels are injected, not historical AP outcomes.
- This iteration has one invoice line per document; later tests must cover multi-line invoices and partial receipts.
- `exception_types` is evaluation ground truth and must never be used as a predictive feature.
- Invalid-vendor rows intentionally appear as `Unknown / invalid vendor` after joining master data.
"""
    (REPORTS / "eda_report.md").write_text(report, encoding="utf-8")
    print("EDA report written successfully.")


if __name__ == "__main__": main()
