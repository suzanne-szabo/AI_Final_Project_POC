# LLM-student fidelity check: Gemma-4-26B-A4B

12 students, style clear, 180 answers (29 on belief probes, 151 neutral). Model calls 209, fallbacks 0, cached share of prompt tokens 93%.

| Measure | Value | Direction |
|---|---|---|
| Belief fidelity (predicted wrong answer given) | 76% | higher is better |
| Leak rate (correct answer despite the belief) | 24% | lower is better |
| Unexpected on belief probes | 0% | lower is better |
| Other misconception's answer | 0% | lower is better |
| Neutral accuracy (correct where beliefs agree with Python) | 100% | higher is better |
| Invented misconception answers | 0% | lower is better |
| Mean confidence: faithful belief answers / leaks / neutral | 4.73 / 5 / 4.97 | |

Per misconception (belief probes it decides):

| Misconception | Answers | Fidelity | Leak | Unexpected |
|---|---|---|---|---|
| A1_LINKED | 4 | 100% | 0% | 0% |
| A2_REVERSED | 3 | 0% | 100% | 0% |
| A3_COPY_ON_ASSIGN | 4 | 100% | 0% | 0% |
| F1_RETURN_IS_PRINT | 4 | 100% | 0% | 0% |
| F2_PARAM_LINKED | 4 | 100% | 0% | 0% |
| F3_DEF_RUNS_BODY | 4 | 100% | 0% | 0% |
| F4_LOCALS_OUTLIVE_CALL | 2 | 100% | 0% | 0% |
| F5_RUNS_AFTER_RETURN | 4 | 0% | 100% | 0% |
