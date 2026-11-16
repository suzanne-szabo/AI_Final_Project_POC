# Week-2 run eval-baseline-eigexplain-llm-100

100 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.15, interpreter llm, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| eig_explain | 0.85 | 0.017 | 8.2 | 2.8 | 0.84 | 0.05 | none |

Per misconception (precision / recall):

| Misconception | eig_explain | Support |
|---|---|---|
| A1_LINKED | 0.93 / 0.93 | 29 |
| A2_REVERSED | 1.00 / 1.00 | 20 |
| A3_COPY_ON_ASSIGN | 0.94 / 0.94 | 18 |
| F1_RETURN_IS_PRINT | 0.87 / 1.00 | 26 |
| F2_PARAM_LINKED | 0.96 / 0.85 | 27 |
| F3_DEF_RUNS_BODY | 0.89 / 1.00 | 16 |
| F4_LOCALS_OUTLIVE_CALL | 1.00 / 1.00 | 18 |
| F5_RUNS_AFTER_RETURN | 0.94 / 1.00 | 17 |
