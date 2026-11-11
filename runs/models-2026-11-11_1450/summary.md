# Interpreter model comparison models-2026-11-11_1450

Labeled explanations x repeats per model, temperature 0, forced tool call. Columns are reported separately for each test set.

## Clean set (48 calls per model)

| Model | Valid calls | Exact match | Precision | Recall | False alarms on correct reasoning | Informative agreement | False alarms on non-informative | Median s | Max s | Cached share of prompt |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3.8-Flash-Next | 1.00 | 1.00 | 1.00 | 1.00 | 0 of 12 | 1.00 | 0 of 2 | 2.1 | 10.0 | 90% |
| Gemma-4-26B-A4B | 1.00 | 1.00 | 1.00 | 1.00 | 0 of 12 | 0.96 | 0 of 2 | 0.8 | 1.3 | 92% |

## Vague set (68 calls per model)

| Model | Valid calls | Exact match | Precision | Recall | False alarms on correct reasoning | Informative agreement | False alarms on non-informative | Median s | Max s | Cached share of prompt |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3.8-Flash-Next | 1.00 | 0.94 | 0.92 | 0.96 | 2 of 14 | 1.00 | 0 of 16 | 1.9 | 6.3 | 95% |
| Gemma-4-26B-A4B | 1.00 | 0.85 | 0.91 | 0.87 | 2 of 14 | 0.88 | 0 of 16 | 0.8 | 1.3 | 98% |
