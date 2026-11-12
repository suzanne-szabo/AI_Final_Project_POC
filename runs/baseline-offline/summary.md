# Week-2 run baseline-offline

100 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.15, interpreter oracle, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| fixed | 0.58 | 0.050 | 10.0 | 0.0 | 0.00 | 0.00 | none |
| eig | 0.80 | 0.024 | 8.6 | 0.0 | 0.73 | 0.08 | none |
| eig_explain | 0.82 | 0.020 | 7.9 | 2.7 | 0.89 | 0.14 | none |

Per misconception (precision / recall):

| Misconception | fixed | eig | eig_explain | Support |
|---|---|---|---|---|
| A1_LINKED | 1.00 / 0.97 | 0.90 / 0.93 | 1.00 / 0.86 | 29 |
| A2_REVERSED | 1.00 / 1.00 | 0.95 / 0.95 | 1.00 / 1.00 | 20 |
| A3_COPY_ON_ASSIGN | 0.64 / 0.39 | 1.00 / 0.83 | 1.00 / 0.89 | 18 |
| F1_RETURN_IS_PRINT | 1.00 / 0.96 | 1.00 / 1.00 | 1.00 / 0.92 | 26 |
| F2_PARAM_LINKED | 0.88 / 0.81 | 0.96 / 0.85 | 1.00 / 0.78 | 27 |
| F3_DEF_RUNS_BODY | 0.87 / 0.81 | 0.94 / 0.94 | 1.00 / 0.88 | 16 |
| F4_LOCALS_OUTLIVE_CALL | 0.88 / 0.83 | 1.00 / 0.89 | 0.94 / 0.94 | 18 |
| F5_RUNS_AFTER_RETURN | n/a / 0.00 | 0.94 / 0.94 | 1.00 / 1.00 | 17 |
