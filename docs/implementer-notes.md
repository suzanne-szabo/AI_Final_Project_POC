# Implementer notes (week 2)

Places where a spec was unclear, contradicted another spec or a test, or left something open. In each
case the tests won over prose. No file in `specs/`, `tests/` or `data/` was changed.

## Ambiguities and choices

- **tools.md §2.1 vs architecture.md §3 (`rank_probes` default `k`).** The schema says `k: int = 3`;
  `Config.rank_k` is "the default number of probes returned by `rank_probes`". *Did:* `k` is optional
  in the schema (`None` → `config.rank_k`, which is 3), range 1–8 when given. Same result with the
  default config. The tool definition gives no JSON default and says "default 3" in its description.
- **tools.md §1 (P3 "wrong types").** *Did:* argument schemas use Pydantic strict mode, so `"3"` or
  `true` for `k` are P3 rejections, not coerced.
- **controller.md §6 (`student_kind`).** Only `bank` / `llm` / `sim` are listed, but tests and the
  model check use `ScriptedStudent`. *Did:* `scripted` for `ScriptedStudent`.
- **controller.md §6 (`step` in call records for the policy actor).** Code policies do not use steps.
  *Did:* for `actor="policy"`, `step` is the number of tool calls handled so far, starting at 1. For the
  model actor it is `steps_used`.
- **controller.md §3 / §2 (`record_no_action`).** The spec does not define the reminder observation or
  which `model` events to write. The tests need both a `reminder` and a `no_action` event. *Did:* every
  reply with no tool call writes `no_action`, and the first one also writes `reminder`. The reminder
  observation has tool `"none"` and no policy id, since it is not one of P1–P8. Only the reminder
  counts as a rejection. The second no-action reply sets `NO_ACTION`.
- **controller.md §3 P1.** *Did:* an accepted `submit_diagnosis` is treated as final for P1 even before
  `check_terminal()` is called, so nothing can run between the accepted submit and the terminal check.
- **controller.md §3 P7 and tools.md (`probes_remaining`).** *Did:* "probes remain" means
  `min(max_probes - len(asked), unasked probes in the bank)`. Observations and the status message use
  the same number.
- **agent.md §3 (graph state).** The spec names `messages` and `pending`. *Did:* added a third
  transient key, `reply`, which carries the model's AIMessage from the `llm` node to the `controller`
  node. `messages` stays append-only through an `operator.add` reducer.
- **agent.md §3 (diagram vs controller.md §4).** The diagram checks the terminal reason between
  `controller` and `tool`. Checking `STEP_LIMIT` there would cancel an approved `submit_diagnosis` on
  the last step, but controller.md §4 says that submit counts. *Did:* when a call is approved, the
  controller node always routes to `tool`. Otherwise it checks the terminal reason (END or `llm`). The
  `tool` node then checks it again.
- **agent.md §3 (P8 ordering).** `test_every_tool_call_gets_exactly_one_tool_message...` needs the
  ToolMessages in call order (c1 before c2). *Did:* when the first call is approved, the extra calls'
  P8 rejections are written in the `tool` node, after the first call runs. Both the messages and the
  trace are then in call order.
- **agent.md §3 (latency and token usage "added to the controller's counters and the `call`
  record").** controller.md §2 has no method for this, and no field is named. *Did:* added
  `Controller.record_model_call(seconds, usage)`, which updates `model_calls` and `model_seconds`. The
  first call record of the step gets a `model` field `{"seconds", "usage"}`, where `usage` is
  `interpret.cache_usage`. `model_calls` counts every attempt, including a failed attempt that is
  retried.
- **agent.md §2, §3 (signatures).** `run_policy_session` and `run_interviewer_session` gained an
  optional trailing `models=None` keyword, so the trace header can record model names. The run command
  passes `interviewer: null` for code deciders.
- **agent.md §5 (tracing).** The header's `tracing.project` is `null` when tracing is off. When it is
  on, the project is `LANGSMITH_PROJECT` or `mental-model-agent`. Per-session metadata (`session_id`,
  `decider`, `student_id`) is attached through `langsmith_extra`.
- **agent.md §6 (scoring of sessions without an estimate).** The spec does not say how `ERROR` or
  `STEP_LIMIT` sessions are scored. *Did:* they count as not an exact match and diagnose nothing. Their
  Brier score uses the last `belief` record (the prior if there is none). This is documented in
  `scoring.py`.
- **agent.md §6 (defaults not stated).** *Did:* `--students 100`, `--seed 7`, `--rate 0.2`,
  `--student-slip 0.15`, `--out runs/week2-<stamp>`. A placeholder key (`your-...`) counts as missing, as
  in `compare_models.py`. `--student llm` also needs `--student-model` (exit 2).
- **agent.md §7 (S1 "ask_probe with the top-ranked probe").** The function `expected(tool_name,
  accepted)` cannot see the arguments. *Did:* `expected` accepts `rank_probes` or `ask_probe`. `Scenario`
  also has `top_probe` (plus `situation` and `expected_text`, beyond the five fields in the spec). The
  script checks the probe id for S1. `state_problems(scenario)` re-checks each stated state before any
  model call. S4 is reached by replaying the top-ranked probe, answered correctly with confidence 5,
  until the belief is confident (7 probes).
- **students.md §3 (hedge draw).** *Did:* the hedge draw is skipped whenever `vague_answer_rate == 0`,
  in any confidence mode. The draws after it are, in order: template, then (informative mode) the
  replacement confidence. `BankStudent.explain` raises `ValueError` if the bank has no entry for the
  drawn clarity.
- **students.md §4 (LLMStudent invalid replies).** Only the valid case's messages are given. *Did:* an
  invalid reply is stored, each of its tool calls gets `ToolMessage("Invalid call.")` so the history
  stays valid for the API, and the reminder follows. A model exception counts as an invalid attempt.
- **tools.md §2.3.** *Did:* an exception from `interpreter.label` is caught and reported as an invalid
  interpreter result with `interpreter_error`, so it is never terminal.
- **architecture.md §4 ("compare_models.py unchanged", "poc.py unchanged") vs agent.md §9 and
  students.md §1.** *Did:* `compare_models.py` follows agent.md §9 and now builds models with
  `mm_agent.llm.make_model`. In `poc.py` only the import line changed (`simstudent` → `students`). Its
  traces are still byte-identical to `runs/poc-2026-11-04/`. `scoring.py` is a new module, and
  `poc.score` is kept, because poc.py must not change.
- **architecture.md §3 (`Config` is frozen).** `slip_by_confidence` is a dict, so `Config` instances
  compare by value but cannot be hashed. The trace header writes the rating keys as strings.

## Observations for the orchestrator (no code change)

- **eig_explain does not reliably beat eig offline.** With 50 students, eig_explain gives exact-match
  scores of 0.86 / 0.68 / 0.78 / 0.76 / 0.68 for seeds 7 / 1 / 2 / 3 / 11. eig gives 0.80 / 0.68 /
  0.80 / 0.74 / 0.70. eig_explain uses about 0.7 fewer probes, and its Brier score is lower only on
  seed 7. Two likely causes in the specified model:
  1. `update_explanation` scores every relevant misconception of the probe (`probe.keys`). A bank
     explanation shows only the misconception that produced the answer (the first in catalog order).
     A second held misconception on the same probe (P01: A1/A2, P03: A2/A3) is therefore treated as
     "not reported" evidence against it.
  2. The explanations make the belief confident sooner, so sessions stop earlier.

  This may matter for week-3 design (for example, scoring only the misconception that matches the
  answer).
