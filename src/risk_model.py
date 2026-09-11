"""Train a dependency-free, regularized invoice risk model and score all invoices."""
from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SEED = 20260911
FEATURES = ["hard_hold", "price_variance", "receipt_variance", "duplicate_candidate", "amount_anomaly", "tax_mismatch", "timing_anomaly", "log_invoice_total"]


def read() -> list[dict]:
    with (OUTPUT / "invoice_control_ledger.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def flag(row: dict, name: str) -> float:
    return float(name in row["flags"].split("|"))


def value(raw: str) -> float:
    try:
        result = float(raw)
        return result if math.isfinite(result) else 5.0
    except (ValueError, TypeError):
        return 0.0


def feature_row(row: dict) -> list[float]:
    return [
        float(row["hard_hold"] == "True"),
        min(value(row["price_variance_pct"]), 5.0),
        min(value(row["receipt_quantity_variance_pct"]), 5.0),
        float(row["duplicate_candidate"] == "True"),
        float(row["amount_anomaly"] == "True"),
        float(row["tax_rate_match"] == "False"),
        float(row["timing_anomaly"] == "True"),
        math.log1p(value(row["invoice_total"])),
    ]


def sigmoid(x: float) -> float:
    x = max(-35.0, min(35.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def split(rows: list[dict]) -> tuple[list[int], list[int]]:
    rng = random.Random(SEED)
    by_label: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows): by_label[row["synthetic_exception"]].append(index)
    train, test = [], []
    for indices in by_label.values():
        rng.shuffle(indices); cut = round(len(indices) * 0.8); train.extend(indices[:cut]); test.extend(indices[cut:])
    return train, test


def fit(matrix: list[list[float]], labels: list[int], train: list[int]) -> tuple[list[float], list[float], list[float]]:
    means = [sum(matrix[i][j] for i in train) / len(train) for j in range(len(FEATURES))]
    scales = [max(1e-6, math.sqrt(sum((matrix[i][j] - means[j]) ** 2 for i in train) / len(train))) for j in range(len(FEATURES))]
    weights = [0.0] * len(FEATURES); intercept = math.log((sum(labels[i] for i in train) + 1) / (len(train) - sum(labels[i] for i in train) + 1))
    for _ in range(1_500):
        gradients, intercept_gradient = [0.0] * len(FEATURES), 0.0
        for i in train:
            x = [(matrix[i][j] - means[j]) / scales[j] for j in range(len(FEATURES))]
            # Keep natural class prevalence for probability calibration. The
            # decision policy, rather than training weights, protects recall.
            error = sigmoid(intercept + sum(w * item for w, item in zip(weights, x))) - labels[i]
            intercept_gradient += error
            for j in range(len(FEATURES)): gradients[j] += error * x[j]
        rate = 0.12 / len(train)
        intercept -= rate * intercept_gradient
        weights = [weight - rate * (gradient + 0.01 * weight) for weight, gradient in zip(weights, gradients)]
    return weights + [intercept], means, scales


def probability(features: list[float], model: list[float], means: list[float], scales: list[float]) -> float:
    standard = [(item - means[i]) / scales[i] for i, item in enumerate(features)]
    return sigmoid(model[-1] + sum(weight * item for weight, item in zip(model[:-1], standard)))


def metrics(rows: list[dict], scores: list[float], indices: list[int]) -> dict:
    predicted = [scores[i] >= 20 for i in indices]  # any non-touchless invoice
    actual = [rows[i]["synthetic_exception"] == "1" for i in indices]
    tp = sum(p and a for p, a in zip(predicted, actual)); fp = sum(p and not a for p, a in zip(predicted, actual)); fn = sum(not p and a for p, a in zip(predicted, actual)); tn = sum(not p and not a for p, a in zip(predicted, actual))
    return {"test_records": len(indices), "precision": round(tp / (tp + fp), 4) if tp + fp else 0, "exception_recall": round(tp / (tp + fn), 4) if tp + fn else 0, "false_approval_rate": round(fn / (fn + tp), 4) if fn + tp else 0, "touchless_processing_rate": round((tn + fn) / len(indices), 4), "confusion_matrix": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn}}


def main() -> None:
    rows = read(); matrix = [feature_row(row) for row in rows]; labels = [int(row["synthetic_exception"]) for row in rows]
    train, test = split(rows); model, means, scales = fit(matrix, labels, train)
    probabilities = [probability(features, model, means, scales) for features in matrix]
    scored = []
    for row, probability_value in zip(rows, probabilities):
        score = round(probability_value * 100)
        # Evidence-bearing controls are safety floors: a statistical estimate
        # may prioritize a queue but must not silently auto-approve a known issue.
        if row["flags"]:
            score = max(score, 25)
        if row["hard_hold"] == "True": score = max(score, 80)
        decision = "HOLD" if score > 60 else ("HUMAN_REVIEW" if score > 20 else "AUTO_APPROVE")
        scored.append({**row, "risk_probability": round(probability_value, 6), "risk_score": score, "risk_decision": decision})
    with (OUTPUT / "invoice_risk_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(scored[0])); writer.writeheader(); writer.writerows(scored)
    evaluation = metrics(rows, [item["risk_score"] for item in scored], test)
    artifact = {"model_type": "regularized_logistic_regression", "seed": SEED, "features": FEATURES, "feature_means": dict(zip(FEATURES, means)), "feature_scales": dict(zip(FEATURES, scales)), "weights": dict(zip(FEATURES + ["intercept"], model)), "training_records": len(train), "evaluation": evaluation, "decision_thresholds": {"auto_approve_max": 20, "human_review_max": 60, "hold_min": 61}, "routing_overrides": {"any_control_flag_min_score": 25, "hard_hold_min_score": 80}, "limitations": ["Synthetic labels and scenario construction can make held-out performance look unrealistically strong.", "The score supports a decision; known control failures cannot be bypassed by the model.", "A production model needs time-based validation, calibrated probabilities, and observed AP outcomes."]}
    (OUTPUT / "risk_model_artifact.json").write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    counts = {name: sum(row["risk_decision"] == name for row in scored) for name in ["AUTO_APPROVE", "HUMAN_REVIEW", "HOLD"]}
    print(f"Risk scoring complete: AUTO_APPROVE={counts['AUTO_APPROVE']:,}, HUMAN_REVIEW={counts['HUMAN_REVIEW']:,}, HOLD={counts['HOLD']:,}; test recall={evaluation['exception_recall']:.1%}.")


if __name__ == "__main__":
    main()
