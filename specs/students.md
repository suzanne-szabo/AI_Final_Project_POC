# Functional Specification: Students and Interpreters (`mm_agent/students.py`, `mm_agent/interpret.py`)

Status: Draft v1 (2026-11-09).

## 1. The `Student` interface (D18)

```python
@dataclass(frozen=True)
class Response:
    answer: str                # what the student says the program prints ("error" allowed)
    confidence: int | None     # 1 (guessing) .. 5 (certain), or None when not collected

class Student(Protocol):
    id: str
    def answer(self, probe: Probe) -> Response: ...
    def explain(self, probe: Probe) -> str: ...
```

- `explain(probe)` explains the student's own earlier answer to that probe. Calling it for a probe the
  student has not answered raises `ValueError`.
- A student never sees the belief state, the answer keys or other students.
- Implementations: `BankStudent` (§3), `LLMStudent` (§4), and `ScriptedStudent` for tests and the model
  check (`specs/agent.md` §8).
- `SimStudent` and `random_profile` from week 1 move here unchanged (only `answer` returning a plain
  string); `poc.py` keeps using them.

## 2. The explanation bank (`data/explanation_bank.jsonl`, D17, D22)

One JSON object per line:

| Field | Type | Meaning |
|---|---|---|
| `id` | str | `B001`, `B002`, … unique |
| `probe_id` | str | The probe being explained |
| `kind` | str | `misconception`, `correct`, `slip` or `none` |
| `misconception` | str or null | For `misconception` entries: the id whose answer key this explains; else null |
| `answer` | str or null | The normalized answer the explanation goes with (`probe.keys[m]` for `misconception`, `probe.correct` for `correct`); null for `slip` and `none` |
| `clarity` | str | `clear` (states the reasoning), `vague` (hedged or partial reasoning), or `none` (reveals nothing: "idk", "I guessed", restating the answer) |
| `holds` | list[str] | Ground truth: what a student who gives this explanation believes. `[misconception]` for misconception entries, `[]` for correct and slip entries; `none` entries are generic and have `holds = null` (they can come from any student) |
| `evident` | list[str] | What the text actually shows: the labels a careful human reader would assign. `clear` misconception entries: `[m]`. `vague` misconception entries: `[m]` if the hint is recognizable, otherwise `[]`. All other entries: `[]` |
| `informative` | bool | Whether the text reveals any reasoning about how the program runs. `false` for every `clarity: none` entry; `true` for clear entries; either for vague entries |
| `text` | str | 1–3 sentences in a beginning student's voice; unique across the bank |

The difference between `holds` and `evident` is what makes vague explanations measurable: a vague
explanation from a student who holds F2 has `holds = ["F2_PARAM_LINKED"]` but may have `evident = []`.
The interpreter is scored against `evident`; the agent's final estimate is scored against `holds`
(through the planted profile).

**Coverage (a test enforces it):** for every probe: for each id in `probe.keys`, at least 1 `clear` and
1 `vague` `misconception` entry; at least 1 `clear` and 1 `vague` `correct` entry; at least 1 `slip`
entry; and at least 1 `none` entry. That is at least 17 × 2 + 15 × 4 = 94 entries for the current bank.
`slip` texts describe a careless error ("I misread which variable got printed") and show no misconception.

**Interpreter test sets (separate from the bank):** `data/explanations.jsonl` (the 24 clean cases) and
`data/explanations_vague.jsonl` (new, at least 30 cases: vague, non-informative, partly wrong, and mixed
explanations that show two misconceptions). Test-set records gain `informative` (bool) and use `labels`
for the evident labels. No text may appear in both the bank and a test set.

`Entry` is a frozen dataclass with exactly the fields in the table above (`holds` is `tuple[str, ...] | None`,
`evident` is `tuple[str, ...]`).

```python
class ExplanationBank:
    @classmethod
    def load(cls, path: Path) -> "ExplanationBank"   # validates every field; ValueError on a bad line
    def entries(self, probe_id: str, kind: str, misconception: str | None = None,
                clarity: str | None = None) -> list[Entry]
    def lookup(self, text: str) -> Entry | None      # exact text match
    def missing(self) -> list[tuple]                  # coverage gaps; [] for a complete bank
```

## 3. `BankStudent`

```python
BankStudent(id: str, profile: frozenset[str], slip: float, rng: random.Random,
            bank: ExplanationBank, confidence_mode: str = "informative")
```

**`answer(probe)`**
1. `intended = probe.intended(profile)`.
2. With probability `1 - slip` the student gives `intended` (not a slip). Otherwise it slips exactly as
   week-1 `SimStudent` does: a uniformly chosen other option, with `OTHER` given as the text
   `"something unexpected"`.
3. Confidence, by `confidence_mode`:

| Mode | Not a slip | Slip |
|---|---|---|
| `informative` | 3: 0.2, 4: 0.4, 5: 0.4 | 1: 0.4, 2: 0.4, 3: 0.2 |
| `uninformative` | 1: 0.1, 2: 0.2, 3: 0.3, 4: 0.25, 5: 0.15 | same as not a slip |
| `none` | `None` | `None` |

4. The student remembers, per probe: the answer given, whether it was a slip, and `intended`.

Random draws happen in a fixed order (slip draw, then the other-option draw if any, then the confidence
draw) so a seeded student is reproducible. With `confidence_mode="none"` there is no confidence draw, so
the answer sequence matches week-1 `SimStudent` for the same seed and slip.

**Vague answers (D24).** With probability `vague_answer_rate` (default 0.15), drawn after the
confidence draw, the student hedges the answer text with one of the fixed templates
`"maybe {a}?"`, `"I think {a}"`, `"{a}, not sure"` (chosen with the student's `rng`). In `informative`
confidence mode a hedged answer's confidence is replaced by 1 or 2 (uniform). With
`vague_answer_rate=0` and `confidence_mode="none"` no extra draws happen (week-1 reproducibility).

**`explain(probe)`** first draws a clarity from `clarity_mix` (default `{"clear": 0.5, "vague": 0.3,
"none": 0.2}`), then chooses uniformly (with the student's `rng`) among bank entries:
- clarity `none`: any `none` entry for the probe;
- otherwise, kind `slip` (any clarity) if that answer was a slip;
- otherwise kind `correct` with the drawn clarity if `intended == probe.correct`;
- otherwise kind `misconception` with the drawn clarity, for the first id in catalog order that is in
  both the profile and `probe.keys` (the misconception that produced `intended`, matching `Probe.intended`).

Constructor additions: `vague_answer_rate: float = 0.15`, `clarity_mix: dict | None = None`.

**Known limitation (to report):** `informative` mode assumes confidence tracks slips. The `uninformative`
mode exists so week 3 can measure how much the design depends on that assumption.

## 4. `LLMStudent` (foundation for LLM vs. LLM runs; D18)

```python
LLMStudent(id: str, profile: frozenset[str], model, max_retries: int = 1)
```

`model` is a LangChain chat model (live or the scripted fake). The student holds an append-only message
list for its whole session.

**Prompt structure (cache rules, D8):**
1. `SystemMessage(STUDENT_SYSTEM_PROMPT)`: a module constant shared by every LLM student. It says: you
   are role-playing a beginning programming student; you are shown short Python programs and predict
   what they print; you hold specific beliefs, some of which may be wrong; always answer according to
   your beliefs, not according to how Python really works; answer only by calling the tools; when asked
   to explain, write 1–3 sentences in a student's voice and never mention a list of beliefs or being an AI.
2. `HumanMessage(beliefs_message(profile))`: the only student-specific part, sent once, second. One line
   per catalog id, in catalog order: the misconception's `summary` if the student holds it, otherwise
   the matching correct statement from `CORRECT_BELIEFS` (below).
3. Then the session's turns, appended only.

`CORRECT_BELIEFS` maps each catalog id to one plain sentence stating the correct rule it replaces, for
example `F4_LOCALS_OUTLIVE_CALL`: "Variables created inside a function stop existing when the call
returns." Eight sentences, one per id, written in `students.py`.

**Tools (bound with `tool_choice="required"`, `parallel_tool_calls=False`, identical on every call):**

| Tool | Arguments |
|---|---|
| `respond` | `answer: str` (1–200 chars; printed lines separated by newlines, or `error`), `confidence: int` (1–5) |
| `explain` | `text: str` (1–400 chars) |

**`answer(probe)`** appends `HumanMessage("What does this program print?\n```python\n{code}\n```\nAlso rate your confidence from 1 (guessing) to 5 (certain).")`,
calls the model, requires exactly one valid `respond` call, appends the `AIMessage` and a
`ToolMessage("Recorded.")`, and returns `Response(answer, confidence)`.

**`explain(probe)`** appends `HumanMessage("Explain why you answered {answer!r} for program {probe.id}.")`,
requires one valid `explain` call, appends the AI and tool messages, and returns the text.

**Failures:** an invalid or missing tool call is retried `max_retries` times with a reminder
(`HumanMessage("Answer by calling the {tool} tool.")`); after that, `answer` returns
`Response("something unexpected", None)` and `explain` returns `"I'm not sure."`, and the student records
the failure (`self.failures` counter) so the run reports it.

**Scope this week:** built and tested offline with the scripted fake model only. Live LLM-student runs
are week-3 work. `LLMStudent` cannot be used with `OracleInterpreter` (its texts are not in the bank); the
run command rejects that combination.

## 5. Interpreters

```python
class Interpreter(Protocol):
    def label(self, probe: Probe, answer: str, explanation: str) -> Evidence: ...
```

`Evidence` is the existing dataclass in `interpret.py` (labels, rationale, valid, error, seconds, usage),
with a new last field `informative: bool = True` (D23).

**`LLMInterpreter(model)`** binds the interpreter tool with `interpret.bind(model)` once at construction and
calls `interpret.interpret(...)`. The prompt-cache rules (D8) still hold.

**Interpreter change (D23).** The `record_evidence` tool gains a required boolean `informative`:
"false when the explanation does not reveal how the student thinks the program runs, for example
'idk', 'I guessed', or only restating the answer". The system prompt adds two rules: an explanation
that is not informative gets `informative: false` and an empty `misconceptions` list; and hedged or
imprecise wording still counts as informative when the reasoning can be recognized. A reply with
`informative: false` and a non-empty list is invalid. The old rule that allowed labeling from the
prediction alone ("a wrong prediction with no explanation of why is weak evidence...") is removed: a
label needs reasoning in the explanation. (Clean-set case E22 is relabeled accordingly.) Because the prompt changes, the interpreter
comparison is rerun on both test sets (D25).

**`OracleInterpreter(bank, sensitivity, false_alarm, rng)`**
1. `entry = bank.lookup(explanation)`. If none: `Evidence([], "", False, "explanation not in bank", 0.0, {})`.
2. If `entry.informative` is false: return `informative=False`, no labels.
3. Otherwise, for each id `m` in `probe.keys`: if `m` is in `entry.evident`, report it with probability
   `sensitivity`; otherwise report it with probability `false_alarm`. Draws in catalog order.
4. Return the reported labels sorted, `valid=True`, `informative=True`, `rationale="oracle"`,
   `seconds=0.0`, `usage={}`.

The oracle stands in for the LLM interpreter in offline runs, with the error rates the belief assumes
(D13, D17). Week 3 compares it with the live interpreter.
