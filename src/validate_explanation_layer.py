"""Validate explanation coverage and evidence grounding."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def main() -> None:
    with (OUTPUT / "invoice_explanations.csv").open(encoding="utf-8", newline="") as handle: rows = list(csv.DictReader(handle))
    assert len(rows) == 10_000
    assert all(row["decision_summary"] and row["evidence_rationale"] for row in rows)
    duplicate = next(row for row in rows if "DUPLICATE_CANDIDATE" in row["flags"])
    price = next(row for row in rows if "PRICE_MISMATCH" in row["flags"])
    approved = next(row for row in rows if row["risk_decision"] == "AUTO_APPROVE")
    assert "matches earlier invoice" in duplicate["evidence_rationale"]
    assert "Unit price" in price["evidence_rationale"]
    assert "No configured" in approved["decision_summary"]
    print("Explanation-layer validation passed.")


if __name__ == "__main__":
    main()
