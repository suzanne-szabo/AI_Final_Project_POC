# Week-2 run smoke-2026-11-11

20 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.15, interpreter llm, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| eig | 0.90 | 0.015 | 8.3 | 0.0 | 0.75 | 0.00 | none |
| eig_explain | 0.90 | 0.013 | 8.1 | 3.1 | 0.90 | 0.05 | none |
| interviewer | 0.75 | 0.029 | 7.9 | 4.5 | 0.90 | 0.20 | none |

Per misconception (precision / recall):

| Misconception | eig | eig_explain | interviewer | Support |
|---|---|---|---|---|
| A1_LINKED | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 6 |
| A2_REVERSED | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 6 |
| A3_COPY_ON_ASSIGN | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 0.86 | 7 |
| F1_RETURN_IS_PRINT | 1.00 / 1.00 | 0.80 / 1.00 | 0.86 / 0.75 | 8 |
| F2_PARAM_LINKED | 0.80 / 0.80 | 1.00 / 1.00 | 1.00 / 1.00 | 5 |
| F3_DEF_RUNS_BODY | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 4 |
| F4_LOCALS_OUTLIVE_CALL | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 6 |
| F5_RUNS_AFTER_RETURN | 1.00 / 1.00 | 0.67 / 1.00 | 0.67 / 1.00 | 2 |

Interviewer:

| Model calls per session | Median latency s | Cached share of prompt | Rejections per session |
|---|---|---|---|
| 21.4 | 0.8 | 79% | 0.20 |
