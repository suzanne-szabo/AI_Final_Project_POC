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
| Week 2: tools, controller, code deciders, LangGraph interviewer, explanation bank, run command | Built, tested offline (specs in `specs/`) |
| Live interviewer model check, interpreter rerun on clean + vague sets | Scripts ready; must run on the Tailscale network (`docs/week2-live-runs.md`) |

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
data/                   explanation bank, clean and vague interpreter test sets
specs/                  week-2 specifications; tests/ black-box tests
docs/decisions.md       decision log; docs/implementer-notes.md spec issues found while implementing
```
