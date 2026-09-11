"""Validate Stage 6 outputs and guard against accidental target leakage."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def main() -> None:
    artifact = json.loads((OUTPUT / "risk_model_artifact.json").read_text())
    with (OUTPUT / "invoice_risk_ledger.csv").open(encoding="utf-8", newline="") as handle: rows = list(csv.DictReader(handle))
    assert len(rows) == 10_000
    assert "synthetic_exception" not in artifact["features"] and "synthetic_exception_types" not in artifact["features"]
    assert all(0 <= int(row["risk_score"]) <= 100 for row in rows)
    assert {row["risk_decision"] for row in rows} <= {"AUTO_APPROVE", "HUMAN_REVIEW", "HOLD"}
    assert artifact["evaluation"]["exception_recall"] >= 0.95
    assert all(int(row["risk_score"]) >= 80 for row in rows if row["hard_hold"] == "True")
    print("Risk-model validation passed.")


if __name__ == "__main__":
    main()
