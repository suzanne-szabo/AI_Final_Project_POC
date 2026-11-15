# LLM-student fidelity check: Gemma-4-26B-A4B

4 students, style clear, 60 answers (6 on belief probes, 54 neutral). Model calls 60, fallbacks 0, cached share of prompt tokens 91%.

| Measure | Value | Direction |
|---|---|---|
| Belief fidelity (predicted wrong answer given) | 83% | higher is better |
| Leak rate (correct answer despite the belief) | 17% | lower is better |
| Unexpected on belief probes | 0% | lower is better |
| Other misconception's answer | 0% | lower is better |
| Neutral accuracy (correct where beliefs agree with Python) | 100% | higher is better |
| Invented misconception answers | 0% | lower is better |
| Mean confidence: faithful belief answers / leaks / neutral | 4.6 / 5 / 4.94 | |

Per misconception (belief probes it decides):

| Misconception | Answers | Fidelity | Leak | Unexpected |
|---|---|---|---|---|
| A3_COPY_ON_ASSIGN | 2 | 100% | 0% | 0% |
| F1_RETURN_IS_PRINT | 2 | 100% | 0% | 0% |
| F2_PARAM_LINKED | 2 | 50% | 50% | 0% |
