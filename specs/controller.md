# Functional Specification: Controller (`mm_agent/controller.py`) and Session (`mm_agent/session.py`)

Status: Draft v1 (2026-11-09). Follows the HW-09 controller pattern.

## 1. Session

```python
Session.new(student: Student, interpreter: Interpreter | None, config: Config,
            session_id: str, decider: str, models: dict[str, str | None] | None = None,
            seed: int | None = None) -> Session
```

Holds: `student`, `interpreter`, `config`, `belief` (a new `Belief(config.prior, config.model_slip)`),
`asked: list[str]` (probe ids in order), `answers: dict[str, Response]`, `last_probe: str | None`,
`explained: set[str]`, `estimate: dict | None`, `outcome: str | None`. Only `tools` changes it.
`interpreter` may be `None` only for deciders that never call `ask_explanation`; calling it then is a
rejection (P6).

## 2. Controller interface

```python
Controller(session: Session, actor: str)          # actor: "model" (interviewer) or "policy" (code decider)
begin_step() -> None                               # model actor only: one model call = one step
validate(tool: str, raw_args: dict) -> Approval | Observation
execute(approval: Approval) -> Observation
handle(tool: str, raw_args: dict) -> Observation   # validate, then execute if approved
reject_extra_call(tool: str, raw_args: dict) -> Observation   # P8
record_thought(text: str) -> None
record_no_action() -> Observation | None           # first time: reminder observation; second in a row: None (terminal)
record_model_error(error: BaseException) -> None
check_terminal() -> Terminal | None
result() -> SessionResult
trace: list[dict]                                  # append-only
```

Value types (frozen dataclasses unless noted):

```python
Approval(tool: str, args: BaseModel, raw_args: dict)
Observation(tool: str, accepted: bool, message: str, data: dict, policy: str | None = None)
    .as_dict() -> dict        # the JSON shape in specs/tools.md §3; "policy" only when rejected
    .to_json() -> str         # json.dumps(as_dict(), sort_keys=True)
Terminal(reason: str, error_kind: str | None = None)     # reason: DIAGNOSED, BUDGET, ERROR, STEP_LIMIT
SessionResult(terminal: str, error_kind: str | None, estimate: dict | None, planted: list[str],
              exact_match: bool | None, probes_used: int, explanations_used: int, steps_used: int,
              rejections_total: int, model_calls: int, model_seconds: float, trace: list[dict])
```

Counters are readable attributes of the controller: `steps_used`, `consecutive_rejections`,
`rejections_total`, `model_calls`, `model_seconds`, plus `terminal: Terminal | None`.
`probes_used` and `explanations_used` are `len(session.asked)` and `len(session.explained)`.

## 3. Policies (checked in this order; the first failure rejects)

| Policy | Rejects |
|---|---|
| P1 | Any call after a terminal reason is set |
| P2 | An unknown tool name |
| P3 | Arguments that fail the tool's schema, including an unknown probe id |
| P4 | `ask_probe` for a probe already asked in this session |
| P5 | `ask_probe` when `len(asked) >= max_probes` (message: the budget is spent, call `submit_diagnosis`) |
| P6 | `ask_explanation` when no probe has been asked, when the last probe was already explained, when `max_explanations` explanations were used, or when the session has no interpreter |
| P7 | `submit_diagnosis` while the belief is not confident and probes remain (`len(asked) < max_probes` and an unasked probe exists) |
| P8 | Every tool call after the first in one model reply |

A rejection changes nothing but the counters and the trace. Each rejected call (P1–P7) increments
`consecutive_rejections`; an accepted call resets it to 0. P8 rejections do not count (the turn's first
call is the one that matters). A reply with no tool call gets one reminder, which counts as a rejection
(HW-09 D24).

## 4. Terminal reasons (checked by `check_terminal()` after every step, first match wins)

1. **`DIAGNOSED`**: this step's accepted `submit_diagnosis` with a confident belief.
2. **`BUDGET`**: this step's accepted `submit_diagnosis` without a confident belief (the budget was spent).
3. **`ERROR`** with one kind:
   - `MODEL_ERROR`: the model call raised, after one retry;
   - `NO_ACTION`: a second consecutive reply with no tool call;
   - `REJECTION_LIMIT`: `consecutive_rejections >= max_consecutive_rejections` (3).
4. **`STEP_LIMIT`**: model actor only, `steps_used >= max_steps` (30).

A valid `submit_diagnosis` on the last allowed step counts, because 1–2 are checked first. Once set, the
terminal reason is final (P1).

## 5. Steps and counters

| Counter | Counts |
|---|---|
| `steps_used` | Model calls (model actor only), including calls that raise or return no tool call |
| `probes_used` | Accepted `ask_probe` calls |
| `explanations_used` | Accepted `ask_explanation` calls |
| `consecutive_rejections`, `rejections_total` | As in §3 |
| `model_calls`, `model_seconds` | Interviewer calls and their total latency (from the agent) |

## 6. Trace

JSONL, one object per line, `sort_keys=True`. Every record has `kind` and `seq` (1, 2, … in order).

| `kind` | Fields |
|---|---|
| `header` | `session_id`, `student_id`, `student_kind` (`bank` / `llm` / `sim`), `planted` (sorted ids; for evaluation, never shown to deciders), `decider` (`fixed` / `shuffled` / `eig` / `eig_explain` / `interviewer`), `models` (`interviewer`, `interpreter`, `student`: names or null), `config` (all fields), `seed` |
| `call` | `step`, `actor`, `tool`, `args` (raw, as received), `accepted`, `policy` (rejections only), `message`, `data`, `probes_used`, `explanations_used`, `steps_used` |
| `belief` | `step`, `after` (tool name), `entropy`, `marginals` (after every accepted `ask_probe` or `ask_explanation`) |
| `model` | `step`, `event` (`thought` / `reminder` / `no_action` / `model_error`), `text` |
| `result` | `terminal`, `error_kind` (or null), `estimate` (or null), `planted`, `exact_match` (or null if no estimate), `probes_used`, `explanations_used`, `steps_used`, `rejections_total`, `model_calls`, `model_seconds` |

The controller appends the `header` record when it is constructed. `planted` is
`sorted(student.profile)` when the student has a `profile` attribute (`BankStudent`, `LLMStudent`,
`SimStudent`), otherwise `[]`. `seed` comes from `Session.new(..., seed=...)` (default `None`).
`result()` may be called once a terminal reason is set; it appends the `result` record and returns the
`SessionResult`.

`SessionResult` carries the same fields as the `result` record plus the full `trace`. `exact_match` is
`set(estimate["most_likely"]) == set(planted)`.
