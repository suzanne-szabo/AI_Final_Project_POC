# Week-2 run eval-baseline-qwen-100-paced

100 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.15, interpreter llm, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| interviewer | 0.84 | 0.017 | 8.3 | 3.2 | 0.83 | 0.07 | none |

Per misconception (precision / recall):

| Misconception | interviewer | Support |
|---|---|---|
| A1_LINKED | 0.96 / 0.93 | 29 |
| A2_REVERSED | 1.00 / 0.95 | 20 |
| A3_COPY_ON_ASSIGN | 0.94 / 0.89 | 18 |
| F1_RETURN_IS_PRINT | 0.93 / 1.00 | 26 |
| F2_PARAM_LINKED | 0.93 / 0.93 | 27 |
| F3_DEF_RUNS_BODY | 0.88 / 0.94 | 16 |
| F4_LOCALS_OUTLIVE_CALL | 1.00 / 1.00 | 18 |
| F5_RUNS_AFTER_RETURN | 0.94 / 1.00 | 17 |

Interviewer:

| Model calls per session | Median latency s | Cached share of prompt | Rejections per session |
|---|---|---|---|
| 18.3 | 2.3 | 80% | 0.03 |
