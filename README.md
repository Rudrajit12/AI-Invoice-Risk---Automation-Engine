# AI Invoice Control Tower

### AI-Powered Invoice Matching, Anomaly Detection, Risk Scoring & AP Automation

> **A decision-support system for Accounts Payable teams designed to maximize safe invoice automation while keeping high-risk transactions under human review.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-150458?logo=pandas)](https://pandas.pydata.org/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-Machine%20Learning-F7931E?logo=scikit-learn)](https://scikit-learn.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?logo=streamlit)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/Plotly-Visualization-3F4F75?logo=plotly)](https://plotly.com/python/)

---

## 1. Project Overview

Accounts Payable teams process thousands of invoices across vendors, purchase orders, goods receipts, and payment systems.

The challenge is not simply **reading an invoice**.

The real challenge is deciding:

> **"Can we safely pay this invoice automatically?"**

This project builds an end-to-end **AI Invoice Control Tower** that combines deterministic financial controls, anomaly detection, machine learning, explainable decisioning, and an operational dashboard.

The system processes an invoice through a sequence of controls:

```text
Invoice
   │
   ▼
Data Validation & Normalization
   │
   ▼
PO / Vendor / Receipt Matching
   │
   ▼
Duplicate & Anomaly Detection
   │
   ▼
Invoice Risk Scoring
   │
   ▼
Evidence-Based Explanation
   │
   ▼
Routing Decision
   │
   ├── AUTO_APPROVE
   ├── HUMAN_REVIEW
   └── HOLD
```

The design principle is **maximum safe automation**, rather than attempting to automate every invoice.

---

# 2. Business Problem

Traditional invoice processing often involves manual verification across multiple systems.

An AP analyst may need to:

* Validate the vendor
* Find the purchase order
* Match invoice lines to PO lines
* Compare quantities
* Check received quantities
* Validate prices
* Check taxes
* Search for duplicate invoices
* Investigate unusual invoice amounts
* Determine whether the invoice should be paid
* Document why an invoice was flagged

At scale, this creates several problems:

### Operational Problems

* High manual workload
* Slow invoice processing
* Repetitive verification
* Inconsistent investigation decisions
* Difficult prioritization of exceptions

### Financial Problems

* Overpayments
* Duplicate payments
* Incorrect quantities
* Price discrepancies
* Tax mismatches
* Payments against invalid POs

### Control Problems

A pure machine-learning system is also insufficient.

A low ML risk score should **never override a deterministic financial control**, such as an invalid PO or a vendor mismatch.

Therefore, this project uses a hybrid architecture:

> **Deterministic controls for hard financial rules + ML for risk prioritization + GenAI for grounded explanations.**

---

# 3. Business Objective

The primary objective is:

## Maximize Safe Automation

Instead of asking:

> "Can AI process every invoice?"

the system asks:

> "Which invoices can be processed automatically with acceptable control risk, and which ones require human intervention?"

The system therefore produces an operational routing decision:

| Risk Score | Routing        | Meaning                                            |
| ---------: | -------------- | -------------------------------------------------- |
|       0–20 | `AUTO_APPROVE` | Low-risk invoice eligible for automation           |
|      21–60 | `HUMAN_REVIEW` | Requires analyst investigation                     |
|     61–100 | `HOLD`         | High-risk invoice should not proceed automatically |

These thresholds are configurable policy defaults.

**Hard financial controls override the ML score.**

---

# 4. Dataset

The project uses a synthetic but relational AP dataset designed to resemble a real invoice-processing environment.

| Dataset         | Records | Purpose                                  |
| --------------- | ------: | ---------------------------------------- |
| Vendors         |     500 | Vendor master data                       |
| Purchase Orders |   5,000 | PO and line-level purchasing information |
| Goods Receipts  |   8,000 | Received quantities                      |
| Invoices        |  10,000 | Invoice transactions                     |
| Payments        |  10,000 | Payment outcomes/events                  |

### Key Relationships

```text
Vendors
   │
   ├───────────────┐
   │               │
   ▼               ▼
Purchase Orders   Invoices
   │               │
   ▼               ▼
Goods Receipts   Payments
```

The data model is intentionally **line-aware**, allowing purchase orders, receipts, and invoices to contain multiple rows.

Document IDs and line IDs are maintained separately to preserve relational integrity.

---

# 5. Dataset Characteristics

The synthetic dataset contains:

* **10,000 invoices**
* **5,000 purchase-order lines**
* **8,000 goods-receipt events**
* **10,000 payment events**
* **500 vendors**

Approximately **28% of invoices were designed to require intervention** in the synthetic dataset.

> This is a synthetic evaluation design and should not be interpreted as a production benchmark.

The dataset includes scenarios such as:

* Valid invoices
* Invalid vendor references
* Invalid PO references
* Vendor mismatches
* Price discrepancies
* Quantity discrepancies
* Receipt quantity violations
* Duplicate invoice candidates
* Vendor amount anomalies
* Tax mismatches
* Timing anomalies

---

# 6. End-to-End Architecture

```text
                         ┌─────────────────────┐
                         │   Source Systems    │
                         ├─────────────────────┤
                         │ Vendor Master       │
                         │ Purchase Orders     │
                         │ Goods Receipts      │
                         │ Invoices            │
                         │ Payments            │
                         └──────────┬──────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────┐
                    │ Data Validation & Normalize │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ Invoice Matching Engine     │
                    ├─────────────────────────────┤
                    │ Vendor validation           │
                    │ PO existence                │
                    │ Vendor / item / currency    │
                    │ Price tolerance              │
                    │ Ordered quantity             │
                    │ Received quantity            │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ Detection Engine            │
                    ├─────────────────────────────┤
                    │ Duplicate candidates        │
                    │ Vendor amount anomalies     │
                    │ Tax mismatches              │
                    │ Timing anomalies            │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ Risk Model                  │
                    │ Regularized Logistic Reg.   │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ Explanation Layer           │
                    │ Evidence-grounded reasons   │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
              ┌──────────────────────────────────────────┐
              │              Decision Engine             │
              ├──────────────────────────────────────────┤
              │ AUTO_APPROVE │ HUMAN_REVIEW │ HOLD       │
              └────────────────────┬─────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ Streamlit Control Tower     │
                    └─────────────────────────────┘
```

---

# 7. Core Control Engine

The matching engine provides explainable, deterministic financial controls.

### Controls implemented

#### Vendor Validation

Checks whether the invoice vendor exists in the vendor master.

```text
Unknown Vendor
      ↓
HARD HOLD
```

#### Purchase Order Validation

Checks whether the referenced PO line exists and belongs to the expected vendor.

#### Vendor / Item / Currency Matching

Checks consistency between:

* Invoice
* Purchase Order
* Vendor
* Item
* Currency

#### Price Matching

Invoice unit price is compared against the PO unit price.

Default tolerance:

```text
±1%
```

#### Quantity Validation

The invoice quantity is checked against:

```text
Invoice Quantity ≤ Ordered Quantity
```

#### Receipt Validation

The invoice quantity is also checked against cumulative received quantity:

```text
Invoice Quantity ≤ Cumulative Received Quantity
```

These controls produce an auditable invoice-level control ledger.

---

# 8. Duplicate & Anomaly Detection

The second layer looks for suspicious or unusual invoice behavior.

## Duplicate Detection

A duplicate candidate is identified when invoices share:

* Vendor
* Supplier invoice reference
* Time window

Default detection window:

```text
7 days
```

The system marks the later candidate for review rather than automatically assuming fraud.

---

## Vendor Amount Anomaly

The system uses vendor-level historical behavior to identify unusually large invoices.

The detection logic incorporates:

* Median Absolute Deviation (MAD)
* Invoice amount
* PO amount

A vendor amount anomaly requires a sufficiently large deviation and a large invoice relative to the valid PO.

---

## Tax Mismatch

The system checks whether invoice tax values are consistent with the expected tax calculation.

---

## Timing Anomaly

Invoices issued substantially after their related PO are flagged.

Default threshold:

```text
>120 days after PO
```

---

# 9. Risk Scoring Model

After deterministic controls and anomaly detection, the invoice is passed to a machine-learning risk model.

### Model

**Regularized Logistic Regression**

Why logistic regression?

Because this project prioritizes:

* Explainability
* Stable behavior
* Transparent feature contribution
* Probability-based risk scoring
* Operational interpretability

The model is intentionally not a black-box model.

---

## Model Features

The risk model uses operational features such as:

* Hard-control indicators
* Price variance
* Receipt variance
* Duplicate candidate
* Vendor amount anomaly
* Tax mismatch
* Timing anomaly
* Log-transformed invoice value

Synthetic label fields such as `exception` and `exception_types` are **not used as predictive features**.

This prevents direct leakage from the synthetic data-generation process.

---

# 10. Decision Policy

The final decision combines model risk with deterministic controls.

```text
                     Invoice
                        │
                        ▼
                Deterministic Controls
                        │
                ┌───────┴────────┐
                │                │
             Hard Hold        No Hard Hold
                │                │
                ▼                ▼
              HOLD          Risk Scoring
                                  │
                     ┌────────────┼────────────┐
                     ▼            ▼            ▼
                  0–20         21–60        61–100
                     │            │            │
                     ▼            ▼            ▼
               AUTO_APPROVE  HUMAN_REVIEW    HOLD
```

### Important Design Principle

The model is **not the final authority**.

For example:

```text
ML Risk Score = 12
PO does not exist
        ↓
HOLD
```

This prevents a low statistical risk score from bypassing a mandatory financial control.

---

# 11. Explainable AI Layer

A risk score alone is not sufficient for an AP analyst.

The system therefore generates an evidence-grounded explanation using the controls and values already recorded in the ledger.

Example:

```text
Decision: HUMAN_REVIEW
Risk Score: 43

Reasons:
• Invoice unit price exceeds PO price tolerance.
• Invoice quantity exceeds cumulative received quantity.
• Invoice was issued outside the expected timing window.

Evidence:
PO Unit Price: ₹1,000
Invoice Unit Price: ₹1,075
Allowed Tolerance: 1%

Invoice Quantity: 120
Received Quantity: 100
```

The explanation layer is deliberately constrained.

It does **not** attempt to infer:

* Fraudulent intent
* Vendor intent
* Employee intent
* Unrecorded business reasons

Instead, explanations are grounded in observable controls and recorded evidence.

---

# 12. Future LLM Integration

The architecture supports an optional LLM explanation layer.

The LLM should receive structured evidence rather than raw unrestricted data.

Example input:

```json
{
  "invoice_id": "INV_001245",
  "decision": "HUMAN_REVIEW",
  "risk_score": 43,
  "flags": [
    "price_variance",
    "receipt_variance"
  ],
  "evidence": {
    "po_unit_price": 1000,
    "invoice_unit_price": 1075,
    "price_tolerance": 0.01,
    "invoice_quantity": 120,
    "received_quantity": 100
  }
}
```

The LLM's role is:

> **Explain the decision — not make or override the decision.**

This keeps the architecture auditable and reduces hallucination risk.

---

# 13. Dashboard

The project includes a Streamlit-based operational dashboard designed as an **AP Control Tower** rather than a generic analytics dashboard.

### Dashboard Pages

#### 1. Executive Overview

Provides:

* Invoice volume
* Invoice value
* Risk distribution
* Automation rate
* Exception value
* Routing breakdown

---

#### 2. Exception Command Center

Designed for AP managers and analysts.

Users can:

* Filter exceptions
* Prioritize high-risk invoices
* Identify major exception types
* Analyze exception value
* Focus investigation effort

---

#### 3. Invoice Investigation

Provides an invoice-level investigation view.

Users can inspect:

* Invoice details
* Vendor
* PO
* Receipt information
* Control failures
* Risk score
* Routing decision
* Explanation

---

#### 4. Vendor Intelligence

Provides vendor-level analysis including:

* Invoice volume
* Invoice value
* Exception behavior
* Anomaly patterns
* Risk distribution

---

#### 5. Automation Performance

Measures the business objective:

> **How much AP work can be automated safely?**

Key metrics include:

* Auto-approval rate
* Human-review rate
* Hold rate
* Exception value
* Risk distribution

---

#### 6. Detection Analytics

Analyzes:

* Duplicate candidates
* Amount anomalies
* Tax mismatches
* Timing anomalies
* Control failures

---

#### 7. Model Evaluation

Provides visibility into:

* Model performance
* Risk distribution
* Routing thresholds
* Model features
* Evaluation metrics

---

# 14. Example Business Insights

The EDA and control analysis reveal several useful patterns in the synthetic environment.

### Exception Value

Exception-linked invoices represent approximately:

**₹4.26B**

out of approximately:

**₹11.07B**

submitted invoice value.

---

### Largest Exception Category by Value

`amount_anomaly` represents approximately:

**₹1.77B**

of invoice value in the synthetic dataset.

---

### Payment Events

Approximately:

**84.5%**

of payment events are marked as paid.

---

### Important Caveat

These figures are **synthetic dataset characteristics**, not real-world AP benchmarks.

They demonstrate the type of operational questions the system can answer rather than claiming production-level performance.

---

# 15. Why This Architecture?

A common approach to AI automation is:

```text
Raw Data → ML Model → Decision
```

This project deliberately uses a different architecture:

```text
Raw Data
   ↓
Deterministic Controls
   ↓
Anomaly Detection
   ↓
Risk Model
   ↓
Decision Policy
   ↓
Grounded Explanation
```

This is more appropriate for financial workflows because some conditions are not probabilistic.

For example:

> A missing PO reference may be a mandatory control failure regardless of what a statistical model predicts.

The architecture therefore separates:

### Rules

"What must never happen?"

### Detection

"What looks unusual?"

### ML

"How risky is this transaction relative to others?"

### GenAI

"How can we explain the evidence clearly?"

---

# 16. Project Structure

```text
ai-invoice-control-tower/
│
├── data/
│   ├── vendors.csv
│   ├── purchase_orders.csv
│   ├── goods_receipts.csv
│   ├── invoices.csv
│   └── payments.csv
│
├── notebooks/
│   ├── 01_data_validation.ipynb
│   ├── 02_eda.ipynb
│   ├── 03_matching_analysis.ipynb
│   ├── 04_anomaly_detection.ipynb
│   └── 05_risk_model.ipynb
│
├── src/
│   ├── app.py
│   ├── matching_engine.py
│   ├── detection_engine.py
│   ├── risk_model.py
│   ├── explanation_layer.py
│   └── ...
│
├── outputs/
│   ├── invoice_match_ledger.csv
│   ├── invoice_control_ledger.csv
│   ├── invoice_explanations.csv
│   └── risk_model_artifact.json
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

# 17. Technology Stack

| Layer                 | Technology                                        |
| --------------------- | ------------------------------------------------- |
| Programming           | Python                                            |
| Data Manipulation     | Pandas, NumPy                                     |
| Visualization         | Plotly                                            |
| Machine Learning      | Scikit-learn                                      |
| Statistical Detection | MAD / rule-based methods                          |
| Dashboard             | Streamlit                                         |
| Data Storage          | CSV / relational model / SQLite-compatible schema |
| Explainability        | Deterministic evidence layer                      |
| Future GenAI          | LLM-based structured explanation                  |
| Version Control       | Git / GitHub                                      |

---

# 18. Getting Started

## Clone the Repository

```bash
git clone https://github.com/<your-username>/ai-invoice-control-tower.git

cd ai-invoice-control-tower
```

## Create Virtual Environment

### Windows

```bash
python -m venv .venv

.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv

source .venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Run the Dashboard

From the project root:

```bash
python -m streamlit run src/app.py
```

The dashboard should open in your browser.

---

# 19. Reproducible Pipeline

The intended processing pipeline is:

```text
Raw CSV Data
     ↓
Data Validation
     ↓
Matching Engine
     ↓
Control Ledger
     ↓
Detection Engine
     ↓
Risk Model
     ↓
Explanation Layer
     ↓
Dashboard
```

Generated artifacts include:

```text
outputs/
├── invoice_match_ledger.csv
├── invoice_control_ledger.csv
├── invoice_explanations.csv
└── risk_model_artifact.json
```

---

# 20. Model Evaluation

The risk model uses a deterministic stratified train/test split:

```text
80% Training
20% Testing
```

The model artifact persists:

* Feature definitions
* Scaling information
* Model coefficients
* Model parameters

### Important Evaluation Caveat

Because the dataset is synthetic and the labels were generated as part of the dataset design, held-out model metrics can be optimistic.

Therefore, model performance should **not** be interpreted as evidence of production fraud-detection accuracy.

A production implementation would require:

* Observed AP outcomes
* Temporal validation
* Probability calibration
* Threshold optimization
* False-positive monitoring
* False-negative monitoring
* Model drift monitoring
* Periodic retraining

---

# 21. Data & ML Governance Considerations

A production deployment should address:

### Data Quality

* Missing vendor information
* Invalid PO references
* Duplicate records
* Currency inconsistencies
* Late-arriving receipts
* Incorrect master data

### Model Risk

* Data drift
* Concept drift
* Calibration
* Threshold stability
* False positives
* False negatives

### Financial Controls

* Hard controls must remain deterministic
* Model scores should not bypass mandatory controls
* Every decision should be auditable

### GenAI Governance

The explanation model should:

* Use structured evidence
* Preserve recorded values
* Preserve decision and score
* Never invent unsupported reasons
* Avoid claims about intent
* Clearly distinguish evidence from interpretation

---

# 22. Key Design Decisions

### 1. Hybrid AI Instead of Pure ML

Financial controls require deterministic logic.

### 2. Explainability Over Model Complexity

Logistic regression was selected to provide transparent risk scoring.

### 3. Evidence Before Explanation

The explanation layer consumes recorded control evidence instead of inventing explanations.

### 4. Human-in-the-Loop

The system is designed to reduce AP workload, not eliminate human judgment.

### 5. Maximum Safe Automation

The goal is not the highest automation percentage.

The goal is:

> **The highest automation rate that remains operationally and financially safe.**

---

# 23. Limitations

This project is a portfolio-grade simulation and has several limitations.

### Synthetic Data

The dataset does not represent real enterprise AP data.

### Synthetic Labels

The exception labels were designed for evaluation and should not be treated as observed production outcomes.

### Simplified Invoice Structure

The current iteration contains one invoice line per document, despite the underlying architecture being line-aware.

### No OCR / Document Extraction

The project starts from structured invoice data.

A production system would need an ingestion layer capable of processing:

* PDF invoices
* Scanned documents
* Email attachments
* EDI
* ERP exports

### No Production ERP Integration

The project does not currently connect directly to systems such as SAP, Oracle, or Microsoft Dynamics.

---

# 24. Future Roadmap

## Phase 1 — Document Intelligence

Add invoice ingestion:

```text
PDF / Image / Email
       ↓
OCR
       ↓
Invoice Field Extraction
       ↓
Structured Invoice
```

---

## Phase 2 — Production Data Layer

Move from CSV files to:

* PostgreSQL
* SQL Server
* Data warehouse
* Event-driven ingestion

---

## Phase 3 — ERP Integration

Integrate with enterprise systems for:

* Purchase orders
* Goods receipts
* Vendor master
* Payment status
* Invoice posting

---

## Phase 4 — Human Review Workflow

Allow AP analysts to:

* Approve
* Reject
* Override
* Request clarification
* Add investigation notes

These outcomes can become future training data.

---

## Phase 5 — Feedback Loop

```text
AI Decision
     ↓
Human Decision
     ↓
Outcome
     ↓
Training Dataset
     ↓
Model Retraining
     ↓
Improved Risk Model
```

This converts the system from a static model into a continuously improving decision-support platform.

---

## Phase 6 — LLM-Powered Investigation Assistant

An analyst could ask:

> "Why is this invoice on hold?"

or:

> "Show me the highest-value vendor exceptions this month."

The assistant would answer using only the underlying structured evidence.

---

# 25. What This Project Demonstrates

This project goes beyond a traditional data-analysis portfolio project.

It demonstrates experience across the complete analytics-to-AI lifecycle:

### Data Engineering

* Relational data modeling
* Data validation
* Entity relationships
* Data quality controls

### Analytics

* Exploratory data analysis
* Exception analysis
* Vendor analysis
* Financial impact analysis

### Machine Learning

* Feature engineering
* Logistic regression
* Regularization
* Train/test evaluation
* Risk scoring

### Anomaly Detection

* Duplicate detection
* Robust statistical methods
* Vendor-level behavioral analysis
* Rule-based anomaly detection

### Explainable AI

* Evidence-based explanations
* Decision traceability
* Human-readable reasoning

### GenAI Architecture

* Structured LLM inputs
* Grounded generation
* Hallucination controls
* Separation of decisioning and explanation

### Product Development

* Streamlit application
* Operational dashboards
* Investigation workflows
* Decision-oriented UX

### Business Thinking

* Automation ROI
* Exception prioritization
* Human-in-the-loop design
* Financial controls
* Operational risk

---

# 26. Disclaimer

This project uses synthetic data created for experimentation and portfolio demonstration.

It is **not intended to provide financial, accounting, fraud, or payment advice**, and its model performance should not be interpreted as production performance.

---

## 🚀 Live Demo

### Try the AI Invoice Control Tower

**[👉 Launch the Live Streamlit App](https://ai-invoice-risk---automation-engine-chww9kshl7cakrmqd86amg.streamlit.app/)**

Explore the deployed application to see how the system combines:

* 📊 **Executive AP Dashboard**
* 🚨 **Exception Command Center**
* 🔎 **Invoice Investigation**
* 🏢 **Vendor Intelligence**
* 🤖 **Automation Performance**
* 🕵️ **Duplicate & Anomaly Detection**
* 📈 **Invoice Risk Scoring & Model Evaluation**
* 💡 **Evidence-Grounded Explanations**

> **Note:** This application uses synthetic invoice, vendor, purchase-order, goods-receipt, and payment data for portfolio demonstration purposes.


---

## Author

**Rudrajit Bhattacharyya**

Data Analyst | AI & Automation

Interested in:

* Applied AI
* Data Analytics
* Machine Learning
* Intelligent Automation
* Decision Systems
* Business Intelligence

---

⭐ **If you found this project interesting, consider starring the repository.**
