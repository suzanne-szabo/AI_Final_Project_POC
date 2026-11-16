# Week-2 run eval-llmstudents-faithful

20 simulated students (llm), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.15, interpreter llm, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| interviewer | 1.00 | 0.000 | 7.0 | 2.2 | 1.00 | 0.00 | none |

Per misconception (precision / recall):

| Misconception | interviewer | Support |
|---|---|---|
| A1_LINKED | 1.00 / 1.00 | 4 |
| A2_REVERSED | n/a / n/a | 0 |
| A3_COPY_ON_ASSIGN | 1.00 / 1.00 | 2 |
| F1_RETURN_IS_PRINT | 1.00 / 1.00 | 5 |
| F2_PARAM_LINKED | 1.00 / 1.00 | 1 |
| F3_DEF_RUNS_BODY | 1.00 / 1.00 | 2 |
| F4_LOCALS_OUTLIVE_CALL | 1.00 / 1.00 | 4 |
| F5_RUNS_AFTER_RETURN | n/a / n/a | 0 |

Interviewer:

| Model calls per session | Median latency s | Cached share of prompt | Rejections per session |
|---|---|---|---|
| 14.9 | 3.0 | 70% | 0.00 |
