# PoC run poc-2026-11-03

100 simulated students, seed 7, plant rate 0.2, student slip 0.15, model slip 0.1, budget 10 probes.

| Policy | Exact profile match | Brier (lower is better) | Mean probes | Ended DIAGNOSED |
|---|---|---|---|---|
| eig | 0.71 | 0.041 | 9.4 | 0.42 |
| fixed | 0.47 | 0.067 | 10.0 | 0.00 |

Per misconception (precision / recall, support):

| Misconception | eig | fixed | Support |
|---|---|---|---|
| A1_LINKED | 0.97 / 0.97 | 1.00 / 0.90 | 29 |
| A2_REVERSED | 0.90 / 0.90 | 0.88 / 0.75 | 20 |
| A3_COPY_ON_ASSIGN | 0.86 / 1.00 | 0.59 / 0.56 | 18 |
| F1_RETURN_IS_PRINT | 0.86 / 0.73 | 0.91 / 0.81 | 26 |
| F2_PARAM_LINKED | 0.86 / 0.89 | 0.93 / 0.96 | 27 |
| F3_DEF_RUNS_BODY | 0.88 / 0.88 | 0.83 / 0.94 | 16 |
| F4_LOCALS_OUTLIVE_CALL | 0.94 / 0.83 | 0.64 / 0.78 | 18 |
| F5_RUNS_AFTER_RETURN | 0.88 / 0.88 | n/a / 0.00 | 17 |
