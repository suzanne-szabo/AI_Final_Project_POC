# Week-2 run eval-offline-500-novague

500 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.0, interpreter oracle, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| eig | 0.81 | 0.023 | 8.4 | 0.0 | 0.81 | 0.10 | none |
| eig_explain | 0.76 | 0.030 | 7.9 | 2.7 | 0.89 | 0.19 | none |

Per misconception (precision / recall):

| Misconception | eig | eig_explain | Support |
|---|---|---|---|
| A1_LINKED | 0.92 / 0.94 | 0.97 / 0.92 | 109 |
| A2_REVERSED | 0.97 / 0.96 | 0.99 / 0.96 | 105 |
| A3_COPY_ON_ASSIGN | 0.90 / 0.89 | 0.92 / 0.84 | 101 |
| F1_RETURN_IS_PRINT | 0.93 / 0.91 | 0.99 / 0.86 | 99 |
| F2_PARAM_LINKED | 0.94 / 0.93 | 0.94 / 0.87 | 107 |
| F3_DEF_RUNS_BODY | 0.98 / 0.95 | 0.99 / 0.84 | 102 |
| F4_LOCALS_OUTLIVE_CALL | 0.97 / 0.93 | 0.95 / 0.87 | 109 |
| F5_RUNS_AFTER_RETURN | 0.92 / 0.93 | 0.96 / 0.78 | 94 |
