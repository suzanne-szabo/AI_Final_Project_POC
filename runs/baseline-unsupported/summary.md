# Week-2 run baseline-unsupported

1 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.15, interpreter oracle, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| interviewer | 0.00 | 0.265 | 0.0 | 0.0 | 0.00 | 0.00 | MODEL_ERROR 1.00 |

Per misconception (precision / recall):

| Misconception | interviewer | Support |
|---|---|---|
| A1_LINKED | n/a / n/a | 0 |
| A2_REVERSED | n/a / 0.00 | 1 |
| A3_COPY_ON_ASSIGN | n/a / n/a | 0 |
| F1_RETURN_IS_PRINT | n/a / 0.00 | 1 |
| F2_PARAM_LINKED | n/a / n/a | 0 |
| F3_DEF_RUNS_BODY | n/a / n/a | 0 |
| F4_LOCALS_OUTLIVE_CALL | n/a / 0.00 | 1 |
| F5_RUNS_AFTER_RETURN | n/a / n/a | 0 |

Interviewer:

| Model calls per session | Median latency s | Cached share of prompt | Rejections per session |
|---|---|---|---|
| 2.0 | n/a | n/a | 0.00 |
