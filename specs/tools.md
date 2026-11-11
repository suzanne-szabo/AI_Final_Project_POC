# Functional Specification: Interviewer Tools (`mm_agent/tools.py`)

Status: Draft v1 (2026-11-09).

## 1. Common rules

- Four tools. Argument schemas are Pydantic models with `extra="forbid"`; wrong types, unknown fields
  and out-of-range values fail validation (controller policy P3).
- `SCHEMAS: dict[str, type[BaseModel]]` maps tool name to schema. `tool_definitions() -> list[dict]`
  returns OpenAI-format tool definitions built once at import, in the fixed order `rank_probes`,
  `ask_probe`, `ask_explanation`, `submit_diagnosis`, serialized deterministically (D8).
- Executors run only calls the controller has approved: `execute(session, tool, args) -> dict`.
  The returned dict is the observation's `data`.
- Every executor that changes the belief is wrapped with `tracing.traceable` (see `agent.md` §5).

## 2. Tools

### 2.1 `rank_probes`
- **Arguments:** `k: int = 3` (1–8).
- **Effect:** read-only. Ranks the unasked probes with `select.rank_probes(session.belief, unasked)`.
- **Data:**
```json
{"ranked": [{"probe_id": "P07", "expected_gain": 0.4123, "targets": ["F2_PARAM_LINKED"]}],
 "marginals": {"A1_LINKED": 0.2, "...": 0.2},
 "probes_used": 3, "probes_remaining": 7, "confident": false}
```
  `targets` is the sorted list of ids in the probe's `keys`. At most `k` entries; fewer if fewer probes remain.

### 2.2 `ask_probe`
- **Arguments:** `probe_id: str` (pattern `^P\d{2}$`, must exist in the bank).
  Required `reason: str` (1–200 characters; D31, required since D32): why this probe was chosen. When the
  interviewer skips the top-ranked probe, the reason says why. A missing or invalid reason is a P3 schema
  rejection. The code deciders pass a fixed reason naming their rule (`policies.POLICY_REASONS`). It does
  not change the effect; it is kept in the trace (the `call` record's `args`) and, when tracing is on, in
  LangSmith.
- **Effect:** `response = student.answer(probe)`; `option = probe.classify(strip_hedges(response.answer))`;
  `belief.update(probe, option, response.confidence if config.use_confidence else None,
  config.slip_by_confidence)`. Records the probe as asked and as the session's *last probe*.
- **Data:**
```json
{"probe_id": "P07", "code": "def bump(n): ...", "answer": "6", "confidence": 5,
 "classified": "6", "answer_matches": ["F2_PARAM_LINKED"],
 "marginals": {"...": 0.0}, "probes_remaining": 6, "confident": false}
```
  `answer_matches` is `["correct"]` if `classified == probe.correct`; the sorted ids `m` with
  `probe.keys[m] == classified` if any; otherwise `["unexpected"]`.
- **`strip_hedges(text) -> str`** (in `probes.py`, D24): lower-cases, then removes the hedge phrases
  `i think`, `i guess`, `maybe`, `probably`, `not sure`, `i'm not sure`, `im not sure`, and any `?`,
  then trims commas and whitespace. Text that is empty after stripping (for example "not sure") stays
  empty and classifies as `OTHER`. `normalize` and `classify` themselves are unchanged (week-1
  reproducibility). Examples: `"maybe 7 5?"` → `"7 5"`; `"6, not sure"` → `"6"`.

### 2.3 `ask_explanation`
- **Arguments:** none.
- **Effect:** for the last probe: `text = student.explain(probe)`;
  `evidence = interpreter.label(probe, last_answer, text)`. **Scope (D27):** if the last answer's
  `answer_matches` names misconceptions, the scored set is those ids; for a `correct` or `unexpected`
  answer it is all of `probe.keys`. If `evidence.valid` and `evidence.informative`:
  `belief.update_explanation(probe, applied, config.interpreter_sensitivity,
  config.interpreter_false_alarm, scope=scored)` where `applied` is the labels in the scored set and
  `ignored` is every other label (D21, D27). If the
  explanation is not informative, or the interpreter failed, the belief is unchanged: "I don't know" is
  not evidence that the student holds no misconception (D23). An interpreter failure is never terminal.
  Marks the last probe as explained.
- **Data:**
```json
{"probe_id": "P07", "explanation": "x is passed in so it goes up too", "interpreter_valid": true,
 "informative": true, "belief_updated": true, "scored": ["F2_PARAM_LINKED"], "labels": ["F2_PARAM_LINKED"], "applied_labels": ["F2_PARAM_LINKED"], "ignored_labels": [],
 "marginals": {"...": 0.0}, "explanations_remaining": 4, "confident": true}
```
  When not valid, `labels`, `applied_labels` and `ignored_labels` are `[]` and an `interpreter_error`
  string is added.

### 2.4 `submit_diagnosis`
- **Arguments:** none.
- **Effect:** stores `session.estimate = belief.estimate()` and the terminal outcome
  (`DIAGNOSED` if the belief is confident, else `BUDGET`). The controller sets the terminal reason.
- **Data:** `{"estimate": {...}, "outcome": "DIAGNOSED"}`.

## 3. Observation shape

The controller wraps every result, accepted or rejected, the same way, and it is sent to the
interviewer as the `ToolMessage` content (JSON, `sort_keys=True`):

```json
{"tool": "ask_probe", "accepted": true, "message": "Answer recorded.", "data": {...}}
{"tool": "submit_diagnosis", "accepted": false, "policy": "P7",
 "message": "Not confident yet: 2 misconceptions are between 0.15 and 0.85, and 4 probes remain.", "data": {}}
```

Rejection messages state what was wrong and what is allowed, with the actual numbers (HW-09 D23 lesson).
