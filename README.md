# Mental-Model Inference Agent

Suzanne Szabo · AI final project (U0-HW-10 onward) and proof of concept for the senior project.

The agent infers a student's mental model of the **Python function-call notional machine**
(assignment as a prerequisite tier, then calls, parameters, locals and `return`) before a lesson begins.
A mental model is represented as the subset of an 8-entry misconception catalog the student holds;
the application keeps an exact Bayesian posterior over all 256 subsets and picks probes that are
expected to reduce its uncertainty most. LLM roles (ReAct interviewer, free-text interpreter) are
constrained: they request typed tool calls, and the application owns the belief state.

## Status (2026-11-18, after U0-HW-12)

| Part | State |
|---|---|
| Catalog (8 misconceptions), 15 probes, exact Bayesian belief, information-gain selection | Built, tested |
| LLM interviewer (LangGraph ReAct, four constrained tools, required stated reason) and LLM interpreter | Built, tested offline; evaluated live (Qwen3.8-Flash-Next chosen as interviewer, D29/C5) |
| Simulated students: bank students, LLM students with beginner personas and styles, fidelity check | Built, tested; LLM students cannot play A2 or F5 (D36, D37) |
| Refinement D34 + D38 (careless-error explanations) | Accepted under the evaluation protocol: 85% → 91% exact match on the same 100 students |
| Evaluation (HW-12) | Protocol `docs/evaluation-protocol.md`; results `docs/evaluation-results.md`; report `report/szabo-suzanne-project-evaluation.pdf` |
| Not built | Lesson engine, student-facing interface, real students, RISC-V (senior project) |

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

## Week-2 sessions: `python -m mm_agent.run`

Offline (no key, no network): simulated `BankStudent`s with explanations from `data/explanation_bank.jsonl`
and the `OracleInterpreter`. Every decider faces the same, identically seeded students.

```bash
uv run python -m mm_agent.run --deciders fixed shuffled eig eig_explain --students 50 --seed 7 --out runs/week2-offline
```

Live (course gateway, `LLM_API_KEY` in `.env`): the LLM interviewer, the LLM interpreter, LLM students.

```bash
uv run python -m mm_agent.run --deciders eig_explain interviewer --interviewer-model Gemma-4-26B-A4B --students 5
uv run python -m mm_agent.run --deciders eig_explain --interpreter llm --students 20
```

Other options: `--confidence-mode informative|uninformative|none`, `--no-use-confidence`,
`--vague-answer-rate`, `--interpreter oracle|llm|none`, `--student bank|llm --student-model NAME`,
`--max-probes`. Invalid combinations exit with code 2 and a message. Output: one trace per decider and
student (`<decider>_sim-NNN.jsonl`), `summary.md`, `summary.json` and `manifest.json`.

Optional LangSmith tracing: set `LANGSMITH_TRACING=true` (see `.env.example`). The JSONL traces stay the
evidence record; tracing never changes prompts or results.

## Live model checks (need the course gateway)

```bash
uv run python scripts/compare_models.py --repeat 2       # interpreter: clean + vague sets (D25)
uv run python scripts/check_interviewer.py --repeat 2    # interviewer: eight fixed scenarios (D16)
```

`compare_models.py` runs `data/explanations.jsonl` (clean) and `data/explanations_vague.jsonl` (vague)
through each model (default `Qwen3.8-Flash-Next` and `Gemma-4-26B-A4B`) and reports every column per set.
`check_interviewer.py` sends each model the exact messages of eight replayed situations (built offline by
`mm_agent/check_scenarios.py`) and reports valid, accepted and expected-action rates. Both write to
`runs/` and accept `--summarize DIR` to rebuild a summary without calling a model. `--repeat 2` shows
whether the prompt prefix is cached.

## Evaluation (U0-HW-12): how to reproduce

The protocol (`docs/evaluation-protocol.md`) defines the success criteria, the eight comparisons C1–C8, every
measure with its direction, the decision rules and the rules for choosing retained cases. All runs use seed 7,
so `sim-NNN` is the same student in every configuration. Baseline runs execute commit `3a00ed7` from a git
worktree that the scripts create at `../final_project_baseline`.

```bash
bash scripts/overnight_eval.sh     # night 1: offline C1, C2, C6; unsupported input (R6); C3 baseline and D34 runs
bash scripts/evening_eval.sh       # night 2: D38 offline and live runs; C3, C4, C5 on 100 students each
uv run python scripts/check_students.py --model Gemma-4-26B-A4B --explain        # LLM-student fidelity check
uv run python -m mm_agent.run --deciders interviewer --interviewer-model Qwen3.8-Flash-Next --interpreter llm \
    --student llm --student-model Gemma-4-26B-A4B --student-style mixed --students 20 \
    --skip-planted A2_REVERSED F5_RUNS_AFTER_RETURN --seed 7 --out runs/eval-llmstudents-faithful    # C7
uv run python scripts/analyze_eval.py   # offline: every table -> docs/evaluation-results.md, runs/eval-analysis.json
```

- **Budget cap.** The course key allows $2 of spending per hour. `scripts/paced_run.py` wraps a run: a session that hits
  the cap is discarded, the script waits 10 minutes, and the session is rerun from a fresh copy of the student
  (waits are logged in `runs/<run>/budget_waits.jsonl`). Agent code is unchanged.
- **Times.** The offline runs take minutes. A 100-student Qwen-interviewer run takes about 1 h 50 min including
  budget waits.
- **LangSmith.** Turned off for the evaluation runs (free tier used up). The JSONL traces are the evidence.
- **Retained cases.** R1–R7 (protocol §6) are listed at the end of `docs/evaluation-results.md`. Each is a trace
  file under `runs/`.

## Layout

```
mm_agent/catalog.py     misconception catalog (the representation of a mental model)
mm_agent/probes.py      probe bank, answer keys, answer normalization, strip_hedges
mm_agent/belief.py      exact posterior over 256 profiles; answer, confidence and explanation evidence
mm_agent/select.py      expected-information-gain ranking; fixed-order baseline
mm_agent/students.py    Student interface, explanation bank, BankStudent, LLMStudent, ScriptedStudent, SimStudent
mm_agent/interpret.py   Interpreter protocol: LLMInterpreter (forced tool call), OracleInterpreter
mm_agent/config.py      Config dataclass, gateway settings
mm_agent/tools.py       the four interviewer tools: schemas, definitions, executors
mm_agent/controller.py  policies P1-P8, terminal reasons, trace
mm_agent/session.py     one session's state
mm_agent/policies.py    code deciders: fixed, shuffled, eig, eig_explain
mm_agent/prompts.py     interviewer system prompt and per-turn status message
mm_agent/agent.py       LangGraph interviewer loop
mm_agent/llm.py         chat-model factory for the course gateway
mm_agent/tracing.py     LangSmith hooks (no-op unless enabled)
mm_agent/scoring.py     scoring against planted profiles
mm_agent/run.py         batch run command
mm_agent/check_scenarios.py  the eight interviewer-check scenarios
mm_agent/poc.py         week-1 proof of concept (kept reproducible)
scripts/compare_models.py    live interpreter comparison
scripts/check_interviewer.py live interviewer model check
scripts/check_students.py   LLM-student fidelity check (mm_agent/fidelity.py)
scripts/overnight_eval.sh, scripts/evening_eval.sh   HW-12 evaluation runs
scripts/paced_run.py        budget-aware wrapper for live runs
scripts/analyze_eval.py     HW-12 analysis -> docs/evaluation-results.md
data/                   explanation bank, clean and vague interpreter test sets
specs/                  week-2 specifications; tests/ black-box tests
docs/decisions.md       decision log (D1-D38); docs/implementer-notes.md spec issues found while implementing
docs/evaluation-protocol.md, docs/evaluation-results.md   HW-12 protocol and results
docs/notional-machine.md, docs/mental-model-representation.md, docs/catalog-sources.md, docs/beginner-sources.md
```
