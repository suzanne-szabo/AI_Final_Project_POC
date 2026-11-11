# Week-2 run trace-check-interviewer

3 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.15, interpreter llm, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| interviewer | 1.00 | 0.001 | 7.3 | 3.0 | 1.00 | 0.00 | none |

Per misconception (precision / recall):

| Misconception | interviewer | Support |
|---|---|---|
| A1_LINKED | 1.00 / 1.00 | 1 |
| A2_REVERSED | 1.00 / 1.00 | 1 |
| A3_COPY_ON_ASSIGN | 1.00 / 1.00 | 1 |
| F1_RETURN_IS_PRINT | 1.00 / 1.00 | 2 |
| F2_PARAM_LINKED | n/a / n/a | 0 |
| F3_DEF_RUNS_BODY | 1.00 / 1.00 | 1 |
| F4_LOCALS_OUTLIVE_CALL | 1.00 / 1.00 | 2 |
| F5_RUNS_AFTER_RETURN | n/a / n/a | 0 |

Interviewer:

| Model calls per session | Median latency s | Cached share of prompt | Rejections per session |
|---|---|---|---|
| 15.3 | 2.6 | 68% | 0.00 |
