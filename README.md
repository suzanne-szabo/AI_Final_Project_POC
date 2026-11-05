# Mental-Model Inference Agent

Suzanne Szabo · AI final project (U0-HW-10 onward) and proof of concept for the senior project.

The agent infers a student's mental model of the **Python function-call notional machine**
(assignment as a prerequisite tier, then calls, parameters, locals and `return`) before a lesson begins.
A mental model is represented as the subset of an 8-entry misconception catalog the student holds;
the application keeps an exact Bayesian posterior over all 256 subsets and picks probes that are
expected to reduce its uncertainty most. LLM roles (ReAct interviewer, free-text interpreter) are
constrained: they request typed tool calls, and the application owns the belief state.

## Status (2026-11-03)

| Part | State |
|---|---|
| Misconception catalog, 15 probes with answer keys | Draft for review (`mm_agent/catalog.py`, `mm_agent/probes.py`) |
| Belief state, information-gain selection, simulated students | Built, tested |
| Code-only proof of concept with JSONL traces | Built; evidence run in `runs/poc-2026-11-04/` (reproducible on Python 3.10–3.13) |
| Evidence interpreter (LLM) with cache-stable prompt | Built, tested offline with a scripted model |
| Model comparison, Qwen vs Gemma | Script ready; must run on the Tailscale network |
| ReAct interviewer (LangGraph) | Week ending Nov 12 |

## Setup

```bash
uv sync
cp .env.example .env        # then put the course key in .env
uv run pytest               # offline; no key needed
```

## Proof of concept (no LLM)

```bash
uv run python -m mm_agent.poc --students 100 --seed 7 --student-slip 0.15 --out runs/poc-2026-11-04
```

The proof of concept uses only the Python standard library, so `python3 -m mm_agent.poc ...` also works
without `uv sync`. The same seed gives byte-identical traces on Python 3.10 through 3.13.

Writes one JSONL trace per student and policy (`eig_*.jsonl`, `fixed_*.jsonl`) plus `summary.md`.
Each trace has a `header` (planted profile, settings), alternating `probe` and `belief` records, and a
`result` (terminal reason, diagnosis, exact match).

## Interpreter model comparison (needs the course gateway)

```bash
uv run python scripts/compare_models.py --repeat 2
```

Runs the 24 labeled explanations in `data/explanations.jsonl` through each model
(default `Qwen3.8-Flash-Next` and `Gemma-4-26B-A4B`) and writes `runs/models-<stamp>/summary.md`.
`--repeat 2` sends each case twice, so the second pass shows whether the prompt prefix is cached.

## Layout

```
mm_agent/catalog.py     misconception catalog (the representation of a mental model)
mm_agent/probes.py      probe bank, answer keys, answer normalization
mm_agent/belief.py      exact posterior over 256 profiles, slip likelihood
mm_agent/select.py      expected-information-gain ranking; fixed-order baseline
mm_agent/simstudent.py  simulated students with planted profiles
mm_agent/poc.py         diagnostic session, scoring, PoC command
mm_agent/interpret.py   LLM evidence interpreter (forced tool call, cache-stable prompt)
scripts/compare_models.py  live model comparison
data/explanations.jsonl    labeled free-text explanations
docs/decisions.md       decision log
```
