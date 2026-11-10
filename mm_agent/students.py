"""Students: the `Student` interface and its implementations (specs/students.md).

- `Response`, `Student`: what every student returns and implements (§1, D18).
- `SimStudent`, `random_profile`: moved here unchanged from week-1 `simstudent.py`, so
  `python -m mm_agent.poc` still reproduces its evidence run byte for byte.
- `Entry`, `ExplanationBank`: the labeled explanation bank (§2, D17, D22).
- `BankStudent`: a planted profile, slips, confidence ratings (D19), hedged answers (D24) and
  explanations drawn from the bank (§3).
- `ScriptedStudent`: fixed responses per probe, for tests and the interviewer check (agent.md §8).
- `LLMStudent`: an LLM role-playing a student through forced tool calls (§4), following the
  prompt-cache rules (D8): one shared constant system prompt, the student-specific beliefs second,
  then append-only turns.

A student sees only the probe's program (and, to explain, its own earlier answer). It never sees the
belief state, the answer keys or other students.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mm_agent.catalog import BY_ID as CATALOG_BY_ID
from mm_agent.catalog import IDS
from mm_agent.probes import BANK, BY_ID, OTHER, Probe
from mm_agent.tracing import traceable

# --- the interface (§1) ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Response:
    answer: str  # what the student says the program prints ("error" allowed)
    confidence: int | None  # 1 (guessing) .. 5 (certain), or None when not collected


@runtime_checkable
class Student(Protocol):
    id: str

    def answer(self, probe: Probe) -> Response: ...

    def explain(self, probe: Probe) -> str: ...


# --- week 1, unchanged ------------------------------------------------------------------------------


@dataclass
class SimStudent:
    """Week-1 simulated student: a planted profile plus random slips.

    A simulated student answers each probe with the answer its profile predicts; with probability
    `slip` it instead gives a different answer chosen uniformly from the probe's other options
    (OTHER stands for an unanticipated answer). `answer` returns a plain string (week-1 interface).
    """

    id: str
    profile: frozenset[str]
    slip: float
    rng: random.Random

    def answer(self, probe: Probe) -> str:
        intended = probe.intended(self.profile)
        if self.rng.random() >= self.slip:
            return intended
        others = [o for o in probe.options() if o != intended]
        choice = self.rng.choice(others)
        return "something unexpected" if choice == OTHER else choice


def random_profile(rng: random.Random, rate: float) -> frozenset[str]:
    return frozenset(m for m in IDS if rng.random() < rate)


# --- the explanation bank (§2) ----------------------------------------------------------------------

KINDS = ("misconception", "correct", "slip", "none")
CLARITIES = ("clear", "vague", "none")
FIELDS = ("id", "probe_id", "kind", "misconception", "answer", "clarity", "holds", "evident", "informative", "text")


@dataclass(frozen=True)
class Entry:
    id: str
    probe_id: str
    kind: str
    misconception: str | None
    answer: str | None
    clarity: str
    holds: tuple[str, ...] | None
    evident: tuple[str, ...]
    informative: bool
    text: str


def _entry_from_record(record: dict) -> Entry:
    """Validate one bank record (every field of the §2 table) and build an Entry; ValueError if bad."""
    if not isinstance(record, dict):
        raise ValueError("record is not a JSON object")
    if set(record) != set(FIELDS):
        raise ValueError(f"fields must be exactly {sorted(FIELDS)}, got {sorted(record)}")
    for name in ("id", "probe_id", "kind", "clarity", "text"):
        if not isinstance(record[name], str) or not record[name].strip():
            raise ValueError(f"{name} must be a non-empty string")
    probe = BY_ID.get(record["probe_id"])
    if probe is None:
        raise ValueError(f"unknown probe_id {record['probe_id']!r}")
    kind, clarity = record["kind"], record["clarity"]
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    if clarity not in CLARITIES:
        raise ValueError(f"clarity must be one of {CLARITIES}, got {clarity!r}")
    if not isinstance(record["informative"], bool):
        raise ValueError("informative must be a boolean")
    evident = record["evident"]
    if not isinstance(evident, list) or any(m not in IDS for m in evident):
        raise ValueError("evident must be a list of catalog ids")
    holds = record["holds"]
    if holds is not None and (not isinstance(holds, list) or any(m not in IDS for m in holds)):
        raise ValueError("holds must be null or a list of catalog ids")
    m = record["misconception"]
    if kind == "misconception":
        if m not in probe.keys:
            raise ValueError(f"misconception {m!r} is not a key of {probe.id}")
        if record["answer"] != probe.keys[m]:
            raise ValueError(f"answer must be {probe.keys[m]!r} for {m} on {probe.id}")
        if holds != [m] or not set(evident) <= {m}:
            raise ValueError("misconception entries need holds == [misconception] and evident within it")
    else:
        if m is not None:
            raise ValueError(f"misconception must be null for kind {kind!r}")
        if kind == "correct" and record["answer"] != probe.correct:
            raise ValueError(f"answer must be {probe.correct!r} for a correct entry on {probe.id}")
        if kind in ("slip", "none") and record["answer"] is not None:
            raise ValueError(f"answer must be null for kind {kind!r}")
        if evident:
            raise ValueError(f"evident must be empty for kind {kind!r}")
        if kind == "none":
            if clarity != "none" or holds is not None or record["informative"]:
                raise ValueError("none entries need clarity none, holds null and informative false")
        elif holds != []:
            raise ValueError(f"holds must be [] for kind {kind!r}")
    if clarity == "none" and record["informative"]:
        raise ValueError("clarity none entries are not informative")
    if clarity == "clear" and not record["informative"]:
        raise ValueError("clear entries are informative")
    return Entry(record["id"], record["probe_id"], kind, m, record["answer"], clarity,
                 None if holds is None else tuple(holds), tuple(evident), record["informative"], record["text"])


class ExplanationBank:
    """The labeled explanations BankStudent draws from and OracleInterpreter looks up."""

    def __init__(self, entries: list[Entry]):
        self._entries = list(entries)
        self._by_text = {e.text: e for e in self._entries}

    @classmethod
    def load(cls, path: Path) -> "ExplanationBank":
        entries: list[Entry] = []
        ids: set[str] = set()
        texts: set[str] = set()
        for number, line in enumerate(Path(path).read_text().splitlines(), start=1):
            if not line.strip():
                continue
            try:
                entry = _entry_from_record(json.loads(line))
            except (ValueError, KeyError) as error:  # json.JSONDecodeError is a ValueError
                raise ValueError(f"{path}:{number}: {error}") from error
            if entry.id in ids or entry.text in texts:
                raise ValueError(f"{path}:{number}: duplicate id or text ({entry.id})")
            ids.add(entry.id)
            texts.add(entry.text)
            entries.append(entry)
        return cls(entries)

    def entries(self, probe_id: str, kind: str, misconception: str | None = None,
                clarity: str | None = None) -> list[Entry]:
        return [e for e in self._entries
                if e.probe_id == probe_id and e.kind == kind
                and (misconception is None or e.misconception == misconception)
                and (clarity is None or e.clarity == clarity)]

    def lookup(self, text: str) -> Entry | None:
        return self._by_text.get(text)

    def missing(self) -> list[tuple]:
        """Coverage gaps as (probe_id, kind, misconception, clarity) tuples; [] for a complete bank."""
        gaps: list[tuple] = []
        for probe in BANK:
            for m in (m for m in IDS if m in probe.keys):
                for clarity in ("clear", "vague"):
                    if not self.entries(probe.id, "misconception", m, clarity):
                        gaps.append((probe.id, "misconception", m, clarity))
            for clarity in ("clear", "vague"):
                if not self.entries(probe.id, "correct", clarity=clarity):
                    gaps.append((probe.id, "correct", None, clarity))
            for kind in ("slip", "none"):
                if not self.entries(probe.id, kind):
                    gaps.append((probe.id, kind, None, None))
        return gaps


# --- BankStudent (§3) --------------------------------------------------------------------------------

CONFIDENCE_TABLES: dict[str, tuple[dict[int, float], dict[int, float]] | None] = {
    # mode: (table when not a slip, table when a slip)
    "informative": ({3: 0.2, 4: 0.4, 5: 0.4}, {1: 0.4, 2: 0.4, 3: 0.2}),
    "uninformative": ({1: 0.1, 2: 0.2, 3: 0.3, 4: 0.25, 5: 0.15},) * 2,
    "none": None,
}
HEDGE_TEMPLATES = ("maybe {a}?", "I think {a}", "{a}, not sure")
DEFAULT_CLARITY_MIX = {"clear": 0.5, "vague": 0.3, "none": 0.2}


def _weighted(rng: random.Random, table: dict) -> object:
    """One draw from a {value: probability} table: a single rng.random(), cumulative in table order."""
    x = rng.random()
    cumulative = 0.0
    items = list(table.items())
    for value, p in items:
        cumulative += p
        if x < cumulative:
            return value
    return items[-1][0]  # rounding: probabilities that sum to just under 1


@dataclass
class _Answered:
    answer: str
    slip: bool
    intended: str


class BankStudent:
    """A simulated student whose explanations come from the labeled bank (specs/students.md §3).

    Random draws happen in a fixed order per answer: slip draw, other-option draw (slips only),
    confidence draw (unless mode "none"), then the hedge draw (only when `vague_answer_rate > 0`),
    the template choice and, in informative mode, the replacement confidence. With
    `confidence_mode="none"` and `vague_answer_rate=0` the answers equal week-1 `SimStudent`'s.
    """

    kind = "bank"

    def __init__(self, id: str, profile: frozenset[str], slip: float, rng: random.Random,
                 bank: ExplanationBank, confidence_mode: str = "informative",
                 vague_answer_rate: float = 0.15, clarity_mix: dict | None = None):
        if confidence_mode not in CONFIDENCE_TABLES:
            raise ValueError(f"confidence_mode must be one of {sorted(CONFIDENCE_TABLES)}")
        mix = dict(DEFAULT_CLARITY_MIX if clarity_mix is None else clarity_mix)
        if any(c not in CLARITIES for c in mix):
            raise ValueError(f"clarity_mix keys must be in {CLARITIES}")
        self.id = id
        self.profile = frozenset(profile)
        self.slip = slip
        self.rng = rng
        self.bank = bank
        self.confidence_mode = confidence_mode
        self.vague_answer_rate = vague_answer_rate
        self.clarity_mix = mix
        self._answered: dict[str, _Answered] = {}

    @traceable(run_type="chain", name="BankStudent.answer")
    def answer(self, probe: Probe) -> Response:
        intended = probe.intended(self.profile)
        slipped = self.rng.random() < self.slip  # same draw and comparison as SimStudent
        text = intended
        if slipped:
            choice = self.rng.choice([o for o in probe.options() if o != intended])
            text = "something unexpected" if choice == OTHER else choice
        tables = CONFIDENCE_TABLES[self.confidence_mode]
        confidence = None if tables is None else _weighted(self.rng, tables[1 if slipped else 0])
        if self.vague_answer_rate > 0 and self.rng.random() < self.vague_answer_rate:
            text = self.rng.choice(HEDGE_TEMPLATES).format(a=text)
            if self.confidence_mode == "informative":
                confidence = self.rng.choice((1, 2))
        self._answered[probe.id] = _Answered(text, slipped, intended)
        return Response(text, confidence)

    @traceable(run_type="chain", name="BankStudent.explain")
    def explain(self, probe: Probe) -> str:
        record = self._answered.get(probe.id)
        if record is None:
            raise ValueError(f"student {self.id} has not answered {probe.id}")
        clarity = _weighted(self.rng, self.clarity_mix)
        if clarity == "none":
            options = self.bank.entries(probe.id, "none")
        elif record.slip:
            options = self.bank.entries(probe.id, "slip")
        elif record.intended == probe.correct:
            options = self.bank.entries(probe.id, "correct", clarity=clarity)
        else:
            m = next(m for m in IDS if m in self.profile and m in probe.keys)
            options = self.bank.entries(probe.id, "misconception", m, clarity)
        if not options:
            raise ValueError(f"the bank has no {clarity} entry for {probe.id} ({self.id})")
        return self.rng.choice(options).text


# --- ScriptedStudent (agent.md §8) -------------------------------------------------------------------


class ScriptedStudent:
    """Returns the scripted response and explanation per probe id; a probe without a script raises KeyError."""

    kind = "scripted"

    def __init__(self, id: str, responses: dict[str, Response], explanations: dict[str, str]):
        self.id = id
        self.responses = dict(responses)
        self.explanations = dict(explanations)
        self._answered: set[str] = set()

    @traceable(run_type="chain", name="ScriptedStudent.answer")
    def answer(self, probe: Probe) -> Response:
        response = self.responses[probe.id]
        self._answered.add(probe.id)
        return response

    @traceable(run_type="chain", name="ScriptedStudent.explain")
    def explain(self, probe: Probe) -> str:
        if probe.id not in self._answered:
            raise ValueError(f"student {self.id} has not answered {probe.id}")
        return self.explanations[probe.id]


# --- LLMStudent (§4) ---------------------------------------------------------------------------------

CORRECT_BELIEFS: dict[str, str] = {
    "A1_LINKED": "After `b = a`, the two variables are independent: assigning a new value to one never changes the other.",
    "A2_REVERSED": "`x = y` copies the value from right to left: y's value goes into x.",
    "A3_COPY_ON_ASSIGN": "`b = a` (or passing a list to a function) makes a second name for the same list, not a copy.",
    "F1_RETURN_IS_PRINT": "`return` hands a value back to the caller without displaying it; `print` displays a value and gives back None.",
    "F2_PARAM_LINKED": "Reassigning a parameter inside a function does not change the caller's variable.",
    "F3_DEF_RUNS_BODY": "A function's body runs only when the function is called, not when the `def` is reached.",
    "F4_LOCALS_OUTLIVE_CALL": "Variables created inside a function stop existing when the call returns.",
    "F5_RUNS_AFTER_RETURN": "`return` ends the function immediately; lines below it in that path do not run.",
}

STUDENT_SYSTEM_PROMPT = """You are role-playing a beginning programming student in an introductory Python course.

You will be shown short Python programs and asked to predict what each one prints. You hold specific \
beliefs about how Python works, listed in the next message; some of them may be wrong. Always answer \
according to your beliefs, not according to how Python really works.

Rules:
- Answer only by calling the tools. To predict output, call respond with what the program prints \
(printed lines separated by newlines, or the word error if you think it crashes) and your confidence \
from 1 (guessing) to 5 (certain).
- When asked to explain an answer, call explain with 1-3 sentences in a student's own voice.
- Never mention a list of beliefs, and never say you are an AI or role-playing."""

STUDENT_TOOLS: list[dict] = [
    {"type": "function", "function": {
        "name": "respond",
        "description": "Give your predicted output for the program and your confidence.",
        "parameters": {"type": "object", "properties": {
            "answer": {"type": "string", "minLength": 1, "maxLength": 200,
                       "description": "What the program prints: printed lines separated by newlines, or error."},
            "confidence": {"type": "integer", "minimum": 1, "maximum": 5,
                           "description": "1 (guessing) to 5 (certain)."}},
            "required": ["answer", "confidence"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "explain",
        "description": "Explain, in your own words, why you gave your answer.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string", "minLength": 1, "maxLength": 400,
                     "description": "1-3 sentences in a student's voice."}},
            "required": ["text"], "additionalProperties": False}}},
]


class _Respond(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: str = Field(min_length=1, max_length=200)
    confidence: int = Field(ge=1, le=5)


class _Explain(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=400)


_STUDENT_SCHEMAS = {"respond": _Respond, "explain": _Explain}


def beliefs_message(profile: frozenset[str]) -> str:
    """The only student-specific message: one belief per catalog id, in catalog order."""
    lines = [CATALOG_BY_ID[m].summary if m in profile else CORRECT_BELIEFS[m] for m in IDS]
    return "Your beliefs about how Python works:\n" + "\n".join(f"- {line}" for line in lines)


class LLMStudent:
    """A chat model playing a student with a planted profile (specs/students.md §4).

    The message list is append-only for the whole session. Each turn needs exactly one valid call of
    the expected tool; an invalid reply is retried `max_retries` times with a reminder, then the
    student falls back (and counts the failure in `self.failures`).
    """

    kind = "llm"

    def __init__(self, id: str, profile: frozenset[str], model, max_retries: int = 1):
        from langchain_core.messages import HumanMessage, SystemMessage

        self.id = id
        self.profile = frozenset(profile)
        self.max_retries = max_retries
        self.failures = 0
        self.bound = model.bind_tools(STUDENT_TOOLS, tool_choice="required", parallel_tool_calls=False)
        self.messages: list = [SystemMessage(STUDENT_SYSTEM_PROMPT), HumanMessage(beliefs_message(self.profile))]
        self._answers: dict[str, str] = {}

    def _turn(self, prompt: str, tool: str) -> BaseModel | None:
        """Append `prompt`, call the model until one valid `tool` call (or retries run out)."""
        from langchain_core.messages import HumanMessage, ToolMessage

        self.messages.append(HumanMessage(prompt))
        for attempt in range(self.max_retries + 1):
            if attempt:
                self.messages.append(HumanMessage(f"Answer by calling the {tool} tool."))
            try:
                reply = self.bound.invoke(list(self.messages))
            except Exception:  # a failed call counts like an invalid reply
                continue
            self.messages.append(reply)
            calls = list(reply.tool_calls or [])
            parsed = None
            if len(calls) == 1 and calls[0]["name"] == tool:
                try:
                    parsed = _STUDENT_SCHEMAS[tool].model_validate(calls[0]["args"])
                except ValidationError:
                    parsed = None
            for call in calls:  # every tool call id gets exactly one tool message
                self.messages.append(ToolMessage("Recorded." if parsed is not None else "Invalid call.",
                                                 tool_call_id=call["id"]))
            if parsed is not None:
                return parsed
        self.failures += 1
        return None

    @traceable(run_type="chain", name="LLMStudent.answer")
    def answer(self, probe: Probe) -> Response:
        prompt = (f"What does this program print?\n```python\n{probe.code}\n```\n"
                  f"Also rate your confidence from 1 (guessing) to 5 (certain).")
        parsed = self._turn(prompt, "respond")
        response = Response(parsed.answer, parsed.confidence) if parsed else Response("something unexpected", None)
        self._answers[probe.id] = response.answer
        return response

    @traceable(run_type="chain", name="LLMStudent.explain")
    def explain(self, probe: Probe) -> str:
        if probe.id not in self._answers:
            raise ValueError(f"student {self.id} has not answered {probe.id}")
        parsed = self._turn(f"Explain why you answered {self._answers[probe.id]!r} for program {probe.id}.",
                            "explain")
        return parsed.text if parsed else "I'm not sure."
