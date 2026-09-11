"""Regression checks for Stage 5 output."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def main() -> None:
    ledger = OUTPUT / "invoice_control_ledger.csv"
    summary_path = OUTPUT / "detection_summary.json"
    assert ledger.exists() and summary_path.exists(), "Run detection_engine.py after matching_engine.py."
    with ledger.open(encoding="utf-8", newline="") as handle: rows = list(csv.DictReader(handle))
    summary = json.loads(summary_path.read_text())
    assert len(rows) == 10_000
    assert {row["control_status"] for row in rows} <= {"PASS", "REVIEW", "HOLD"}
    for signal in ["DUPLICATE_CANDIDATE", "VENDOR_AMOUNT_ANOMALY", "TAX_RATE_MISMATCH", "TIMING_ANOMALY"]:
        assert summary["new_signal_counts"][signal] > 0, f"missing signal: {signal}"
    assert summary["exceptions_captured"] >= 2_600
    print("Duplicate and anomaly detection validation passed.")


if __name__ == "__main__":
    main()
