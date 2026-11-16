# Week-2 run eval-baseline-qwen-100

100 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.15, interpreter llm, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| interviewer | 0.27 | 0.115 | 2.8 | 1.1 | 0.27 | 0.02 | MODEL_ERROR 0.67 |

Per misconception (precision / recall):

| Misconception | interviewer | Support |
|---|---|---|
| A1_LINKED | 1.00 / 0.31 | 29 |
| A2_REVERSED | 1.00 / 0.35 | 20 |
| A3_COPY_ON_ASSIGN | 0.90 / 0.50 | 18 |
| F1_RETURN_IS_PRINT | 0.83 / 0.38 | 26 |
| F2_PARAM_LINKED | 1.00 / 0.30 | 27 |
| F3_DEF_RUNS_BODY | 1.00 / 0.31 | 16 |
| F4_LOCALS_OUTLIVE_CALL | 1.00 / 0.33 | 18 |
| F5_RUNS_AFTER_RETURN | 0.80 / 0.24 | 17 |

Interviewer:

| Model calls per session | Median latency s | Cached share of prompt | Rejections per session |
|---|---|---|---|
| 7.6 | 3.0 | 73% | 0.01 |
