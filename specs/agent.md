# Functional Specification: Deciders, Interviewer Loop, Prompts, Tracing, Run Command, Model Check

Status: Draft v1 (2026-11-09).

## 1. Deciders

A decider chooses the next tool call. All deciders act only through `Controller` and produce the same
trace format.

| Decider | Module | Explains? |
|---|---|---|
| `fixed` | `policies` | no |
| `shuffled` | `policies` | no |
| `eig` | `policies` | no |
| `eig_explain` | `policies` | yes |
| `interviewer` | `agent` (LLM) | its choice |

## 2. Code deciders (`mm_agent/policies.py`)

```python
run_policy_session(student, decider: str, config: Config, interpreter=None,
                   session_id: str = "", seed: int | None = None, shuffle_rng=None) -> SessionResult
```

Uses a `Controller` with `actor="policy"` and calls `controller.handle(...)` for every action. Loop:

1. Choose the next probe:
   - `fixed`: the first unasked probe in bank order;
   - `shuffled`: the first unasked probe in a permutation of the bank drawn once per session with
     `shuffle_rng` (default `random.Random(f"{seed}-{student.id}-shuffle")`);
   - `eig`, `eig_explain`: the top probe from `select.rank_probes(belief, unasked)` (D11 tie-break).
2. `ask_probe(probe_id)`.
3. `eig_explain` only: if `answer_matches != ["correct"]` and explanations remain, `ask_explanation()`.
4. If the belief is confident, or `max_probes` probes have been asked, or no probe is left:
   `submit_diagnosis()` and stop. Otherwise go to 1.

**Regression requirement:** `eig` with a `BankStudent` in `confidence_mode="none"`, `use_confidence=False`,
and the week-1 seeding (§6) reaches the same `most_likely` set as `poc.diagnose` for every student of
`--students 100 --seed 7 --student-slip 0.15`.

## 3. Interviewer loop (`mm_agent/agent.py`)

LangGraph `StateGraph`, as in HW-09:

```
START -> llm -> controller --(terminal set)--> END
                    |
                    v
                  tool -> continue? --(terminal)--> END
                              |
                              +--(otherwise)--> llm
```

- **Graph state:** `messages` (the stored, append-only history) and `pending` (the approved call). The
  `Session` and `Controller` are passed through LangGraph's run config, never through graph state.
- **`llm` node:** `controller.begin_step()`; sends
  `[SystemMessage(SYSTEM_PROMPT), HumanMessage(OPENING)] + messages + [HumanMessage(status_message(...))]`.
  The status message is rebuilt every turn and **not stored** (D8). The model is bound once with
  `tool_definitions()`, `tool_choice="required"`, `parallel_tool_calls=False`. One retry on an exception,
  then `record_model_error` (terminal). Latency and token usage (including cached tokens, as in
  `interpret.cache_usage`) are added to the controller's counters and the `call` record.
- **`controller` node:** stores the `AIMessage`. Text content is recorded as a `thought`. No tool call:
  `record_no_action()`; on the first occurrence a constant reminder `HumanMessage` is stored. The first
  tool call is validated; each extra call gets a P8 rejection. **Every tool call id receives exactly one
  `ToolMessage`**, accepted or rejected.
- **`tool` node:** executes the approved call and stores its `ToolMessage`.
- **`continue?`:** `check_terminal()`.
- `recursion_limit = 4 * max_steps + 10`, so the controller's step limit always ends the session first.

```python
run_interviewer_session(student, config: Config, model, interpreter,
                        session_id: str = "", seed: int | None = None) -> SessionResult
```

Passing the scripted fake chat model (`tests/fakes.py`, as in HW-09) makes a session deterministic.

## 4. Prompts (`mm_agent/prompts.py`)

**`SYSTEM_PROMPT`** (module constant; nothing run-specific, no limits, no model names):
- Role: find out how a beginning student thinks Python executes function calls, by asking short
  tracing questions. The result is a hypothesis about the student's mental model, not a grade.
- The catalog: one line per id with its `summary`.
- Process: start with `rank_probes`; usually ask the top-ranked probe; when choosing a lower-ranked one,
  state why in `ask_probe`'s `reason` argument (D31; for example, to settle an assignment misconception
  before a function one that depends on it); call `ask_explanation` right after an answer that matches a misconception, an
  unexpected answer, or any answer with confidence 2 or lower, because the explanation separates a real
  belief from a careless slip; do **not** ask after a correct answer given with confidence 3 or higher,
  because it rarely reveals anything and spends the limited explanation budget (D30); call
  `submit_diagnosis` when the status says the belief is confident or the probe budget is spent.
- Rules: exactly one tool call per turn; never reply with text only; do not assume what the student
  believes beyond the observations; the student sees only the programs.

**`OPENING`**: the constant first user message, `"Begin the session."`

**`status_message(session, controller) -> str`**, appended last every turn, for example:
```
Step 5 of 30. Probes used 2 of 10. Explanations used 1 of 5.
Belief confident: no. Uncertain (between 0.15 and 0.85): F2_PARAM_LINKED 0.82, A1_LINKED 0.40.
Last probe: P07 (explanation available).
```
Adds `"The probe budget is spent: call submit_diagnosis."` when no probe may be asked, and
`"This is your last step: call submit_diagnosis if it will be accepted."` on the last step.

## 5. LangSmith tracing (`mm_agent/tracing.py`, D14)

- `traceable(**kwargs)`: `langsmith.traceable` when the `langsmith` package imports, else a no-op
  decorator. LangSmith itself sends nothing unless `LANGSMITH_TRACING=true`.
- `tracing_enabled() -> bool`: true when `LANGSMITH_TRACING` is `true` or `1` (case-insensitive).
- Decorated: the tool executors (`run_type="tool"`), `Interpreter.label` implementations, `Student.answer`
  and `Student.explain` implementations, `run_policy_session` and `run_interviewer_session`
  (`run_type="chain"`, with metadata `session_id`, `decider`, `student_id`). LangChain and LangGraph
  calls are traced automatically when the variable is set.
- The trace header records `"tracing": {"langsmith": bool, "project": str | null}` (never the key).
- `.env.example` gains commented `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`
  (default project `mental-model-agent`).
- Tracing must not change prompts, tool definitions, observations or results (a test checks prompts
  and a seeded policy session with the variable unset and set to `false`).

## 6. Run command (`mm_agent/run.py`)

```
python -m mm_agent.run --deciders eig eig_explain [interviewer] --students 100 --seed 7
    [--rate 0.2] [--student-slip 0.15] [--student bank|llm] [--confidence-mode informative|uninformative|none]
    [--no-use-confidence] [--vague-answer-rate 0.15] [--interpreter oracle|llm|none] [--interviewer-model NAME]
    [--interpreter-model NAME] [--student-model NAME] [--max-probes 10] [--out DIR]
```

- **Students and seeding (as week 1):** profiles from `random.Random(seed)` with
  `random_profile(rng, rate)` for `sim-000`, `sim-001`, …; each student's own `rng` is
  `random.Random(f"{seed}-{student_id}")`; the oracle's is `random.Random(f"{seed}-{student_id}-oracle")`.
  Every decider faces freshly built, identically seeded students.
- **Defaults:** `--interpreter oracle`, `--student bank`, `--confidence-mode informative`; model names
  default to D12 for the interpreter and are required for `interviewer` and `--student llm`.
- **Settings:** `main` reads `.env` first, for every run (offline too), without overriding variables that
  are already set, so the LangSmith variables apply to offline runs as well (fix found 2026-11-11).
- **Exit codes:** `main(argv) -> int` returns 0 on success; invalid options return 2 after printing a message (it does not raise).
- **Rejected combinations (exit code 2 with a message):** `interviewer` without `--interviewer-model`;
  `eig_explain` or `interviewer` with `--interpreter none`; `--student llm` with `--interpreter oracle`;
  any LLM option without a non-empty `LLM_API_KEY` (from the environment or `.env`).
- **Output:** `DIR/<decider>_<student_id>.jsonl`; `DIR/summary.md` and `summary.json`; `DIR/manifest.json`
  (command line, git commit if available, config, models, start and end time, tracing on or off).
- **Summary per decider:** exact profile match; Brier score; per-misconception precision and recall;
  mean probes; mean explanations; `DIAGNOSED` rate; confident-but-wrong rate (`DIAGNOSED` with a wrong
  set); error rate by kind; and for the interviewer, model calls per session, median latency, cached
  share of prompt tokens, rejections per session. Scoring lives in `mm_agent/scoring.py`.

## 7. Interviewer model check (`scripts/check_interviewer.py`, D16)

A small live task run before the smoke test, to choose the interviewer model.

```
uv run python scripts/check_interviewer.py [--models Qwen3.8-Flash-Next Gemma-4-26B-A4B] [--repeat 2]
```

Eight scenarios. Each is built by replaying a fixed sequence of actions through a real `Controller` with a
`ScriptedStudent` (§8) to produce exactly the messages the interviewer would see; then the model makes
**one** call. The controller validates it (without executing it).

| # | Situation | Expected action(s) |
|---|---|---|
| S1 | Session start | `rank_probes`, or `ask_probe` with the top-ranked probe |
| S2 | Last answer matches a misconception, confidence 5 | `ask_explanation` |
| S3 | Last answer was unexpected | `ask_explanation` |
| S4 | Belief confident | `submit_diagnosis` |
| S5 | Two probes asked, not confident | anything except `submit_diagnosis` |
| S6 | Probe budget spent (`max_probes=3`) | `submit_diagnosis` |
| S7 | Last answer correct, confidence 5 | `rank_probes` or `ask_probe` |
| S8 | Previous call was rejected (probe already asked) | an accepted call |

The scenarios are built by a function the tests can import without a network:
`build_scenarios() -> list[Scenario]` in `mm_agent/check_scenarios.py`, where
`Scenario(name, session, controller, messages, expected)` holds the replayed session and controller, the
exact message list the interviewer would be sent (system prompt, opening, stored history, status
message), and `expected`, a function `(tool_name, accepted) -> bool`. The script imports it and adds
only the live model calls and the report. The script checks that each built scenario is in the stated state (for example, S4's belief really is
confident) before calling a model. Output: `runs/interviewer-check-<stamp>/<model>.jsonl` (one record per
call: scenario, tool, args, valid, accepted, expected, seconds, usage) and `summary.md` with, per model:
valid single tool call rate, accepted rate, expected-action rate, median latency, cached share.

## 8. `ScriptedStudent` (for tests and the model check)

`ScriptedStudent(id, responses: dict[str, Response], explanations: dict[str, str])` in `students.py`:
returns the given response and explanation per probe id; a probe without a script raises `KeyError`.

## 9. Interpreter comparison update (`scripts/compare_models.py`, D25)

- `--cases` accepts one or more files; the default is both `data/explanations.jsonl` (clean) and
  `data/explanations_vague.jsonl` (vague). Each record carries `informative` (the clean set's records are
  all `true`; the loader treats a missing field as `true`).
- New per-call fields: `informative_expected`, `informative_predicted`, `set` (`clean` or `vague`).
- The summary reports every existing column separately for each set, plus: agreement on `informative`,
  and false alarms on non-informative cases (labels reported for an explanation that reveals nothing).
- `--summarize DIR` keeps working on old runs (missing fields count as clean and informative).
- The run is repeated for Qwen3.8-Flash-Next and Gemma-4-26B-A4B before any interviewer smoke test, and
  its measured rates on the vague set replace the conservative D13 rates in `Config` only by an
  orchestrator decision.
