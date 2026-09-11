# Stage 6 — Invoice risk model

The Stage 6 baseline is a regularized logistic regression implemented with the Python standard library. It trains on a deterministic stratified 80/20 split and persists feature scaling and weights in `outputs/risk_model_artifact.json`.

## Inputs

The model uses operational controls, not synthetic labels: hard holds, price and receipt variance, duplicate candidate, vendor amount anomaly, tax mismatch, timing anomaly, and log invoice value. `synthetic_exception` and `synthetic_exception_types` are explicitly excluded from model features and only support held-out evaluation.

## Routing policy

| Risk score | Route |
| ---: | --- |
| 0–20 | `AUTO_APPROVE` |
| 21–60 | `HUMAN_REVIEW` |
| 61–100 | `HOLD` |

Any deterministic control flag raises the score to at least 25, so it cannot be silently auto-approved. A hard hold raises the score to at least 80 and cannot be bypassed by the model. The initial thresholds are policy defaults. Production calibration must balance financial leakage from false approvals against analyst-review cost and capacity.

## Important interpretation

The synthetic dataset intentionally maps exception scenarios to control signals, so held-out model metrics are optimistic. Before production use, retrain on observed AP outcomes, validate over time, calibrate predicted probabilities, and monitor drift.
