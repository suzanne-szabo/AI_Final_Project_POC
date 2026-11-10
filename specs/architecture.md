# Architecture Specification: Mental-Model Inference Agent (Week 2)

Status: **Draft v2 (2026-11-10): approved v1 plus vague responses (D22–D25)**
Owner (design authority): Suzanne Szabo
Implementation: specifications and black-box tests by Claude with the orchestrator; module code by a
fresh coding agent working only from `specs/` and `tests/` (D15).

This document fixes the module boundaries, owned state, public interfaces and allowed interactions for
week 2. Each new module has its own functional specification:

| Spec | Covers |
|---|---|
| `specs/belief.md` | Evidence from explanations and confidence ratings |
| `specs/students.md` | The `Student` interface, the explanation bank, `BankStudent`, `LLMStudent` |
| `specs/tools.md` | The four interviewer tools, their argument schemas and observations |
| `specs/controller.md` | Policies, steps, terminal reasons, trace |
| `specs/agent.md` | The code policies, the LangGraph interviewer, prompts, LangSmith, the run command, the model check |

Black-box tests are derived from these specifications before any agent code is written.

---

## 1. Goals and design principles

1. **The application owns all state.** The belief state, the probes asked, the counters, the trace and
   the terminal reason belong to the application. LLMs only request typed tool calls (interviewer,
   student) or return typed labels (interpreter).
2. **Validate before execute.** Every tool call is checked by the controller first. A rejected call
   changes nothing except the step count, the rejection count and the trace.
3. **Only the application decides how a session ends.** A session ends with a mental-model estimate only
   when the controller accepts `submit_diagnosis`, and it accepts it only when the belief is confident or
   the probe budget is spent.
4. **One loop, many deciders.** The code policies (fixed, shuffled, information gain, information gain
   with explanations) and the LLM interviewer all act through the same tools and controller and write
   the same trace format, so they can be compared fairly (week 3).
5. **One student interface, many students.** A simulated student from the labeled bank and an
   LLM-played student implement the same `Student` interface, so any decider can face any student.
   This is the foundation for running an LLM interviewer against an LLM student (D18).
6. **Offline first.** Every module can run with no network: a scripted fake chat model, the
   `OracleInterpreter`, and `BankStudent`. Live services are used only by the run command and the
   model-check script.
7. **Prompt-cache rules (D8) apply to every LLM call:** constant system prompts and tool definitions,
   variable content last, append-only history, no sliding window.
8. **The JSONL trace is the evidence record.** LangSmith (D14) is an optional viewer switched on by
   environment variables; it must never change prompts or results.

## 2. Conventions shared by all modules

| Item | Convention |
|---|---|
| Misconception id | An id from `mm_agent/catalog.py`, such as `F4_LOCALS_OUTLIVE_CALL` |
| Probe id | `P01` to `P15` from `mm_agent/probes.py` |
| Relevant misconceptions of a probe | The ids in that probe's `keys` (the misconceptions it can detect) |
| Answer | Free text from the student; compared after `probes.normalize` and `Probe.classify` |
| Confidence | An integer 1 (guessing) to 5 (certain), or `None` when not collected |
| Probability | Rounded to 4 decimals in observations and traces |
| Marginals | `Belief.marginals()`: P(student holds m) for every catalog id, in catalog order |
| Confident belief | Every marginal is `<= low` (0.15) or `>= high` (0.85) |
| JSON | Observations and trace records are JSON objects serialized with `sort_keys=True` |

## 3. Configuration

One frozen dataclass, `mm_agent.config.Config`, replaces `poc.SessionConfig`. All fields have defaults.

| Field | Default | Meaning |
|---|---|---|
| `max_probes` | 10 | Probe budget per session |
| `max_explanations` | 5 | Explanation budget per session |
| `max_steps` | 30 | Model calls per interviewer session (code policies do not use steps) |
| `max_consecutive_rejections` | 3 | Rejections in a row that end an interviewer session |
| `low`, `high` | 0.15, 0.85 | Confidence thresholds for the belief |
| `prior` | 0.2 | Prior probability of each misconception |
| `model_slip` | 0.10 | Slip rate when no confidence rating is used |
| `use_confidence` | `True` | Whether answer likelihoods use the student's confidence rating |
| `slip_by_confidence` | `{1: 0.35, 2: 0.20, 3: 0.10, 4: 0.06, 5: 0.04}` | Slip rate used for each rating |
| `interpreter_sensitivity` | 0.85 | P(interpreter reports m \| student holds m) (D13) |
| `interpreter_false_alarm` | 0.05 | P(interpreter reports m \| student does not hold m) (D13) |
| `rank_k` | 3 | Default number of probes returned by `rank_probes` |

## 4. Module overview

```
mm_agent/
  catalog.py      Misconception catalog                                        (built, unchanged)
  probes.py       Probe bank, answer keys, normalize/classify                   (built, unchanged)
  belief.py       Exact posterior over 256 profiles; + explanation and confidence evidence   (extend)
  select.py       Expected information gain, rank_probes                        (built, unchanged)
  config.py       Config dataclass, settings from .env                          (new)
  students.py     Student protocol, Response, ExplanationBank, BankStudent, LLMStudent  (new; replaces simstudent.py)
  interpret.py    LLM interpreter; + Interpreter protocol, LLMInterpreter, OracleInterpreter  (extend)
  tools.py        Tool argument schemas and executors                           (new)
  controller.py   Policies, counters, trace, terminal reason                    (new)
  session.py      Composition root for one session                              (new)
  policies.py     Code deciders: fixed, shuffled, eig, eig_explain               (new)
  prompts.py      Interviewer system prompt and per-turn status message         (new)
  llm.py          Chat-model factory for the course gateway                     (new)
  agent.py        LangGraph interviewer loop                                    (new)
  tracing.py      LangSmith hooks, no-op unless enabled                         (new)
  scoring.py      Scoring of finished sessions against planted profiles         (new; moved from poc.py)
  run.py          python -m mm_agent.run: batch sessions, traces, summary       (new)
  check_scenarios.py  The eight interviewer-check scenarios (see agent.md §7)    (new)
  poc.py          Week-1 proof of concept, kept so its evidence stays reproducible  (unchanged)
data/
  explanations.jsonl        24 labeled explanations: interpreter test set (unchanged)
  explanation_bank.jsonl    Labeled explanations used by BankStudent (new; see students.md)
  explanations_vague.jsonl  Vague, non-informative and mixed explanations: second interpreter test set (new)
scripts/
  compare_models.py         Interpreter model comparison (unchanged)
  check_interviewer.py      Small model check for the interviewer role (new; see agent.md §7)
```

`simstudent.py` is removed; `poc.py` imports `SimStudent` and `random_profile` from `students.py`, where
they are kept unchanged so the week-1 evidence run still reproduces byte for byte.

## 5. Modules: responsibility, owned state, interface, dependencies

### 5.1 `belief` (extended)
- **Responsibility:** the exact posterior over all 256 profiles.
- **New interface:** `update(probe, option, confidence=None, slip_by_confidence=None)` uses the slip for
  the given rating; `update_explanation(probe, labels, sensitivity, false_alarm)`.
- **Owned state:** the profile weights. Only `tools` calls the update methods. Detail: `specs/belief.md`.

### 5.2 `students`
- **Responsibility:** produce a student's answer, confidence rating and explanation for a probe.
- **Interface:** the `Student` protocol (`id`, `answer(probe) -> Response`, `explain(probe) -> str`),
  implemented by `BankStudent` and `LLMStudent`. Detail: `specs/students.md`.
- **Owned state:** each student's own memory of its earlier answers. Students never see the belief state.

### 5.3 `interpret` (extended)
- **Responsibility:** map an explanation onto catalog labels.
- **Interface:** the `Interpreter` protocol, `label(probe, answer, explanation) -> Evidence`, implemented by
  `LLMInterpreter` (the existing forced-tool-call interpreter, model chosen in D12) and `OracleInterpreter`
  (ground-truth labels from the bank, with configurable noise). Detail: `specs/students.md` §5.

### 5.4 `tools`, `controller`, `session`
- `tools`: four tools (`rank_probes`, `ask_probe`, `ask_explanation`, `submit_diagnosis`), Pydantic
  argument schemas, and executors that run an *already approved* call. Detail: `specs/tools.md`.
- `controller`: the single gatekeeper and the only code that sets the terminal reason. Owns the counters
  and the append-only trace. Detail: `specs/controller.md`.
- `session`: holds one session's student, belief, interpreter, config, the probes asked, the
  explanations asked and the final estimate. Only `tools` changes it.

### 5.5 `policies`, `agent`, `prompts`, `llm`, `tracing`, `run`
- `policies`: code deciders that act through `Controller.handle(...)`. Detail: `specs/agent.md` §2.
- `agent`: the LangGraph interviewer loop. Detail: `specs/agent.md` §3–4.
- `prompts`: the interviewer's constant system prompt and per-turn status message. Detail: `specs/agent.md` §4.
- `llm`: `make_model(model_name)` returns `ChatOpenAI` for the course gateway, `temperature=0`,
  `max_retries=0`, timeout 180 s (as HW-09).
- `tracing`: LangSmith hooks. Detail: `specs/agent.md` §5.
- `run`: the batch command and summary. Detail: `specs/agent.md` §6.

## 6. Allowed interactions

| From → To | Allowed? | Notes |
|---|---|---|
| any LLM → anything | ✖ | LLMs only produce messages; application code interprets them |
| `agent`, `policies` → `controller` | ✔ | The only route by which a decision reaches state |
| `agent`, `policies` → `session`, `belief`, `students` | ✖ | Deciders never touch state directly. `policies` may read `session.belief` (read-only) to choose a probe, like the information-gain rule |
| `controller` → `tools` | ✔ | Only after the policy checks pass |
| `tools` → `belief`, `students`, `interpret` | ✔ | The only code that updates the belief or questions a student |
| `students` → `belief`, `controller` | ✖ | Students see only the probe |
| `interpret` → `belief` | ✖ | It returns labels; `tools` applies them |
| tests → public interfaces | ✔ | Black-box tests use only interfaces in the specs |

**What the interviewer sees:** its system prompt, its own earlier tool calls with their observations,
and the per-turn status message. It never sees the planted profile, the answer keys or the student's
internal state.

**What a student sees:** only the probe's program and, for an explanation, its own earlier answer.

## 7. Terminal reasons (summary; full detail in `specs/controller.md`)

Checked after every step, first match wins: `DIAGNOSED` (accepted `submit_diagnosis` with a confident
belief), `BUDGET` (accepted `submit_diagnosis` after the probe budget is spent without confidence),
`ERROR` with a kind (`MODEL_ERROR`, `NO_ACTION`, `REJECTION_LIMIT`), `STEP_LIMIT`.

## 8. Decision log for this specification

Recorded in `docs/decisions.md` as D15–D26.

| # | Decision |
|---|---|
| D15 | Spec-first process kept: Claude writes specs and black-box tests, a fresh coding agent implements (as HW-08/09) |
| D16 | The interviewer model is chosen after a small model check of Qwen and Gemma (`scripts/check_interviewer.py`) and before the smoke test |
| D17 | Simulated explanations come from a labeled explanation bank; offline runs use an `OracleInterpreter` with the D13 noise rates |
| D18 | A common `Student` interface, with an `LLMStudent` built now (offline-tested) so LLM interviewer vs. LLM student runs are possible in week 3 |
| D19 | Confidence ratings: every answer carries a 1–5 rating, which sets the slip rate used in the answer likelihood; switchable for ablation |
| D20 | A shuffled-order baseline joins fixed order and information gain |
| D21 | Explanation labels count only for the probe's relevant misconceptions; other labels are recorded but not applied |
| D22 | The bank has clear, vague and non-informative explanations, with `holds` (belief) separate from `evident` (what the text shows); a vague interpreter test set is added |
| D23 | The interpreter reports whether an explanation is informative; non-informative explanations leave the belief unchanged |
| D24 | Simulated students sometimes hedge answers; `strip_hedges` runs before classification |
| D25 | The Qwen vs. Gemma interpreter comparison is rerun on clean and vague sets with the new prompt |
| D26 | Catalog sources and evidence levels recorded in `docs/catalog-sources.md` |
