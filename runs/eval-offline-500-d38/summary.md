# Week-2 run eval-offline-500-d38

500 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.15, interpreter oracle, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| eig_explain | 0.80 | 0.025 | 8.3 | 2.8 | 0.81 | 0.13 | none |

Per misconception (precision / recall):

| Misconception | eig_explain | Support |
|---|---|---|
| A1_LINKED | 0.98 / 0.95 | 109 |
| A2_REVERSED | 0.98 / 0.96 | 105 |
| A3_COPY_ON_ASSIGN | 0.98 / 0.82 | 101 |
| F1_RETURN_IS_PRINT | 0.94 / 0.94 | 99 |
| F2_PARAM_LINKED | 0.97 / 0.84 | 107 |
| F3_DEF_RUNS_BODY | 0.96 / 0.85 | 102 |
| F4_LOCALS_OUTLIVE_CALL | 0.97 / 0.90 | 109 |
| F5_RUNS_AFTER_RETURN | 0.93 / 0.93 | 94 |
