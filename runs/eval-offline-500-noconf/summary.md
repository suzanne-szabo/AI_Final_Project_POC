# Week-2 run eval-offline-500-noconf

500 simulated students (bank), seed 7, plant rate 0.2, student slip 0.15, confidence mode informative (used: False), vague answer rate 0.15, interpreter oracle, budget 10 probes / 5 explanations.

| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations | Ended DIAGNOSED | Confident but wrong | Errors |
|---|---|---|---|---|---|---|---|
| eig | 0.70 | 0.038 | 9.2 | 0.0 | 0.48 | 0.09 | none |
| eig_explain | 0.73 | 0.035 | 8.2 | 2.8 | 0.79 | 0.18 | none |

Per misconception (precision / recall):

| Misconception | eig | eig_explain | Support |
|---|---|---|---|
| A1_LINKED | 0.86 / 0.93 | 0.96 / 0.91 | 109 |
| A2_REVERSED | 0.97 / 0.94 | 0.94 / 0.95 | 105 |
| A3_COPY_ON_ASSIGN | 0.82 / 0.86 | 0.96 / 0.81 | 101 |
| F1_RETURN_IS_PRINT | 0.89 / 0.84 | 0.94 / 0.93 | 99 |
| F2_PARAM_LINKED | 0.90 / 0.87 | 0.95 / 0.78 | 107 |
| F3_DEF_RUNS_BODY | 0.94 / 0.86 | 0.94 / 0.80 | 102 |
| F4_LOCALS_OUTLIVE_CALL | 0.93 / 0.84 | 0.93 / 0.90 | 109 |
| F5_RUNS_AFTER_RETURN | 0.91 / 0.97 | 0.91 / 0.85 | 94 |
