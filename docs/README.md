
# AI Invoice Control Tower — Streamlit Dashboard

This dashboard sits on top of the existing invoice-control pipeline.

## Expected project layout

```text
invoice_control_dashboard/
├── app.py
├── requirements.txt
├── data/
│   ├── vendors.csv
│   ├── purchase_orders.csv
│   ├── goods_receipts.csv
│   ├── invoices.csv
│   └── payments.csv
└── outputs/
    ├── invoice_control_ledger.csv
    ├── invoice_match_ledger.csv
    ├── invoice_explanations.csv
    └── risk_model_artifact.json
```

The dashboard **prefers the generated output files**. If `invoice_control_ledger.csv`
is not present, it creates a lightweight fallback ledger from the raw CSVs so the UI
can still be explored.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL shown by Streamlit.

## Pages

1. Executive Overview
2. Exception Command Center
3. Invoice Investigation
4. Vendor Intelligence
5. Automation Performance
6. Detection Analytics
7. Model Evaluation

## Important design choice

The operational pages do not use the synthetic `exception` or `exception_types`
labels to make routing decisions. Those labels are used only on the development
Model Evaluation page.

For production-like testing, place the actual pipeline outputs in `outputs/`.

## Next production step

Replace the CSV loader with the canonical SQLite/PostgreSQL data model and expose
the control ledger through a service/API. The UI should remain a presentation layer,
not the location of business rules.
