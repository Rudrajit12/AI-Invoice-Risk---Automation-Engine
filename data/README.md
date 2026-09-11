# Synthetic data

Generated CSV files are written to `data/synthetic/` by:

```powershell
python src/generate_synthetic_data.py
python src/validate_data.py
```

The generator is deterministic (`seed = 20260911`). It produces 500 vendors, 5,000 POs, 8,000 receipt events, 10,000 invoices, and one payment lifecycle event per invoice. The invoice scenarios and their counts are recorded in `manifest.json`.

The files are intentionally safe for demos and development: they contain no personal, customer, or real vendor data.
