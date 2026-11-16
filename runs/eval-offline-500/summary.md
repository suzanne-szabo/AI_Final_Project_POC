# Week-2 run eval-offline-500

500 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: True), vague answer rate 0.15, interpreter oracle, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| fixed | 0.57 | 0.051 | 10.0 | 0.0 | 0.00 | 0.00 | none |
| shuffled | 0.63 | 0.046 | 9.9 | 0.0 | 0.12 | 0.01 | none |
| eig | 0.76 | 0.027 | 8.6 | 0.0 | 0.74 | 0.11 | none |
| eig_explain | 0.75 | 0.031 | 8.0 | 2.7 | 0.88 | 0.19 | none |

Per misconception (precision / recall):

| Misconception | fixed | shuffled | eig | eig_explain | Support |
|---|---|---|---|---|---|
| A1_LINKED | 0.97 / 0.95 | 0.92 / 0.84 | 0.90 / 0.94 | 0.98 / 0.92 | 109 |
| A2_REVERSED | 0.97 / 0.99 | 0.95 / 0.83 | 0.97 / 0.92 | 0.98 / 0.95 | 105 |
| A3_COPY_ON_ASSIGN | 0.78 / 0.61 | 0.90 / 0.77 | 0.85 / 0.83 | 0.99 / 0.78 | 101 |
| F1_RETURN_IS_PRINT | 0.96 / 0.92 | 0.89 / 0.74 | 0.97 / 0.93 | 0.95 / 0.90 | 99 |
| F2_PARAM_LINKED | 0.85 / 0.79 | 0.89 / 0.80 | 0.94 / 0.89 | 0.96 / 0.77 | 107 |
| F3_DEF_RUNS_BODY | 0.96 / 0.89 | 0.88 / 0.81 | 0.98 / 0.87 | 0.98 / 0.79 | 102 |
| F4_LOCALS_OUTLIVE_CALL | 0.85 / 0.83 | 0.91 / 0.76 | 0.95 / 0.86 | 0.96 / 0.91 | 109 |
| F5_RUNS_AFTER_RETURN | n/a / 0.00 | 0.87 / 0.85 | 0.98 / 0.96 | 0.94 / 0.87 | 94 |
