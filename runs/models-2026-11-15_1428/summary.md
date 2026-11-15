# Interpreter model comparison models-2026-11-15_1428

Labeled explanations x repeats per model, temperature 0, forced tool call. Columns are reported separately for each test set.

## Vague set (43 calls per model)

| Model | Valid calls | Exact match | Precision | Recall | False alarms on correct reasoning | Informative agreement | False alarms on non-informative | Median s | Max s | Cached share of prompt |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3.8-Flash-Next | 0.98 | 0.95 | 0.96 | 1.00 | 1 of 15 | 0.98 | 0 of 9 | 2.2 | 7.6 | 91% |
