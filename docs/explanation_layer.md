# Stage 7 — Grounded explanation layer

`src/explanation_layer.py` converts the risk ledger into reviewer-ready language at `outputs/invoice_explanations.csv`. Every reason is derived from a recorded control, value, identifier, or threshold. It does not infer fraud, vendor intent, or facts outside the source data.

## LLM-ready contract

An optional future LLM receives only the structured evidence for one invoice and must:

1. State the existing decision and score without changing them.
2. Explain only supplied flags and evidence values.
3. Use conditional language such as “requires review” rather than alleging fraud.
4. Return an empty rationale only when no evidence is supplied; never invent a reason.
5. Preserve invoice IDs, PO IDs, prices, quantities, and thresholds exactly.

Suggested response structure:

```json
{
  "decision_summary": "One concise sentence matching the supplied route.",
  "reasons": ["One evidence-grounded sentence per supplied flag"],
  "recommended_action": "Resolve, compare, or verify the named source record."
}
```

The deterministic implementation remains the production-safe fallback when an LLM is unavailable, slow, or returns an invalid response.
