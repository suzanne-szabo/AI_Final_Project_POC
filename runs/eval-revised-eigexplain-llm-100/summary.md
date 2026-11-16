# Week-2 run eval-revised-eigexplain-llm-100

100 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.15, interpreter llm, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| eig_explain | 0.85 | 0.017 | 7.7 | 2.6 | 0.91 | 0.11 | none |

Per misconception (precision / recall):

| Misconception | eig_explain | Support |
|---|---|---|
| A1_LINKED | 1.00 / 0.90 | 29 |
| A2_REVERSED | 1.00 / 1.00 | 20 |
| A3_COPY_ON_ASSIGN | 1.00 / 0.94 | 18 |
| F1_RETURN_IS_PRINT | 0.96 / 0.96 | 26 |
| F2_PARAM_LINKED | 1.00 / 0.81 | 27 |
| F3_DEF_RUNS_BODY | 1.00 / 0.94 | 16 |
| F4_LOCALS_OUTLIVE_CALL | 1.00 / 0.94 | 18 |
| F5_RUNS_AFTER_RETURN | 1.00 / 0.88 | 17 |
