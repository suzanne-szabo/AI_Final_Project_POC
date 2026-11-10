"""The evidence interpreter: one stateless LLM call that maps a student's free-text explanation
onto catalog labels through a forced `record_evidence` tool call.

Prompt-cache rules (architecture D8). Providers cache the longest byte-identical prefix of a request,
so every call must share as long an identical prefix as possible:
1. SYSTEM_PROMPT and TOOL are module constants built once from the catalog. Nothing variable
   (no timestamps, ids, counters, model name or run settings) is ever placed in them.
2. The tool definition is serialized deterministically (fixed key order) and bound the same way
   on every call, because tool definitions are part of the cached prefix.
3. Everything that varies (the probe code, the student's answer and explanation) goes in the one
   user message at the very end.
A test asserts that two different cases produce identical system prompts and tool definitions.

Week 2 (specs/students.md §5):
- The tool gains a required boolean `informative` (D23); a non-informative reply must have an empty
  label list. The old rule that allowed labeling from the prediction alone is removed.
- `Evidence` gains a last field `informative: bool = True`.
- The `Interpreter` protocol, with `LLMInterpreter` (this module's forced-tool-call interpreter,
  bound once) and `OracleInterpreter` (the bank's `evident` labels with the D13 noise rates, for
  offline runs, D17).
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field, ValidationError

from mm_agent.catalog import CATALOG, IDS
from mm_agent.probes import Probe
from mm_agent.tracing import traceable

if TYPE_CHECKING:
    from mm_agent.students import ExplanationBank

TOOL_NAME = "record_evidence"


class RecordEvidence(BaseModel):
    misconceptions: list[str] = Field(default_factory=list, max_length=3)
    rationale: str = Field(max_length=400)
    informative: bool

    def checked(self) -> "RecordEvidence":
        if not self.informative and self.misconceptions:
            raise ValueError("informative is false but misconceptions were reported")
        unknown = [m for m in self.misconceptions if m not in IDS]
        if unknown:
            raise ValueError(f"unknown misconception ids: {unknown}")
        if len(set(self.misconceptions)) != len(self.misconceptions):
            raise ValueError("duplicate misconception ids")
        return self


TOOL: dict = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Record which catalog misconceptions the student's explanation shows evidence of.",
        "parameters": {
            "type": "object",
            "properties": {
                "misconceptions": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(IDS)},
                    "maxItems": 3,
                    "description": "Ids of misconceptions clearly shown by the explanation. Empty if the "
                                   "reasoning is correct or shows none of them.",
                },
                "rationale": {
                    "type": "string",
                    "maxLength": 400,
                    "description": "One or two sentences citing the student's words that justify the labels.",
                },
                "informative": {
                    "type": "boolean",
                    "description": "false when the explanation does not reveal how the student thinks the "
                                   "program runs, for example 'idk', 'I guessed', or only restating the answer.",
                },
            },
            "required": ["misconceptions", "rationale", "informative"],
            "additionalProperties": False,
        },
    },
}

_catalog_lines = "\n".join(
    f"- {m.id} ({m.tier} tier): {m.summary} Typical signal: {m.signal}" for m in CATALOG
)

SYSTEM_PROMPT = f"""You analyze how an introductory programming student thinks Python executes code.

The student was shown a short Python program, predicted what it prints, and explained their \
reasoning. Decide which of the catalog misconceptions below their explanation clearly shows, using \
the notional machine of Python: names are bound to objects; assignment binds a name and never \
copies; a call creates a new frame whose parameters are bound to the argument objects; local names \
disappear when the call returns; return ends the call immediately and hands a value back to the \
caller without displaying it.

Misconception catalog:
{_catalog_lines}

Rules:
- Label only what the explanation shows. A label needs reasoning in the explanation; the predicted \
output alone is not enough.
- If the explanation does not reveal how the student thinks the program runs (for example "idk", \
"I guessed", or only restating the answer), set informative to false and give an empty misconceptions \
list.
- Hedged or imprecise wording still counts as informative when the reasoning can be recognized; label \
the misconception it shows.
- Correct reasoning gets an empty list, even if worded informally.
- Use at most three ids, never ids outside the catalog.
- Respond only by calling {TOOL_NAME} exactly once."""


def user_message(probe: Probe, answer: str, explanation: str) -> str:
    """The only part of the request that varies between calls; always sent last."""
    return (f"Program:\n```python\n{probe.code}\n```\n\n"
            f"Student's predicted output: {answer}\n\n"
            f"Student's explanation: {explanation}")


def tool_definition_bytes() -> str:
    return json.dumps(TOOL, separators=(",", ":"))  # insertion order is fixed by the literal above


@dataclass
class Evidence:
    labels: list[str]
    rationale: str
    valid: bool
    error: str | None
    seconds: float
    usage: dict = field(default_factory=dict)
    informative: bool = True  # D23


def cache_usage(reply) -> dict:
    """Token usage including cached prompt tokens when the gateway reports them."""
    usage = getattr(reply, "usage_metadata", None) or {}
    details = usage.get("input_token_details") or {}
    meta = (getattr(reply, "response_metadata", None) or {}).get("token_usage") or {}
    prompt_details = meta.get("prompt_tokens_details") or {}
    cached = details.get("cache_read", prompt_details.get("cached_tokens"))
    return {"input_tokens": usage.get("input_tokens", meta.get("prompt_tokens")),
            "output_tokens": usage.get("output_tokens", meta.get("completion_tokens")),
            "cached_tokens": cached}


def bind(model):
    """Bind the tool identically for every call (part of the cache rules)."""
    return model.bind_tools([TOOL], tool_choice="required", parallel_tool_calls=False)


def interpret(bound_model, probe: Probe, answer: str, explanation: str) -> Evidence:
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(user_message(probe, answer, explanation))]
    started = time.monotonic()
    try:
        reply = bound_model.invoke(messages)
    except Exception as error:  # recorded, not raised: a batch must survive one failed call
        return Evidence([], "", False, f"MODEL_ERROR {type(error).__name__}: {error}",
                        time.monotonic() - started)
    seconds = time.monotonic() - started
    usage = cache_usage(reply)
    calls = [c for c in reply.tool_calls if c["name"] == TOOL_NAME]
    if len(reply.tool_calls) != 1 or not calls:
        return Evidence([], "", False, f"expected one {TOOL_NAME} call, got {len(reply.tool_calls)}",
                        seconds, usage)
    try:
        evidence = RecordEvidence.model_validate(calls[0]["args"]).checked()
    except (ValidationError, ValueError) as error:
        return Evidence([], "", False, f"invalid arguments: {error}", seconds, usage)
    return Evidence(sorted(evidence.misconceptions), evidence.rationale, True, None, seconds, usage,
                    evidence.informative)


class Interpreter(Protocol):
    """Maps an explanation onto catalog labels (specs/students.md §5)."""

    def label(self, probe: Probe, answer: str, explanation: str) -> Evidence: ...


class LLMInterpreter:
    """The forced-tool-call interpreter. The tool is bound once at construction (D8)."""

    def __init__(self, model):
        self.bound = bind(model)

    @traceable(run_type="chain", name="LLMInterpreter.label")
    def label(self, probe: Probe, answer: str, explanation: str) -> Evidence:
        return interpret(self.bound, probe, answer, explanation)


class OracleInterpreter:
    """Ground-truth labels from the explanation bank with configurable noise (D13, D17).

    For a bank text that is informative, each of the probe's relevant misconceptions is reported with
    probability `sensitivity` if the text shows it (`evident`) and `false_alarm` otherwise; draws in
    catalog order from `rng`. Texts not in the bank give an invalid Evidence.
    """

    def __init__(self, bank: "ExplanationBank", sensitivity: float, false_alarm: float, rng: random.Random):
        self.bank = bank
        self.sensitivity = sensitivity
        self.false_alarm = false_alarm
        self.rng = rng

    @traceable(run_type="chain", name="OracleInterpreter.label")
    def label(self, probe: Probe, answer: str, explanation: str) -> Evidence:
        entry = self.bank.lookup(explanation)
        if entry is None:
            return Evidence([], "", False, "explanation not in bank", 0.0, {})
        if not entry.informative:
            return Evidence([], "oracle", True, None, 0.0, {}, False)
        reported = []
        for m in IDS:
            if m in probe.keys:
                rate = self.sensitivity if m in entry.evident else self.false_alarm
                if self.rng.random() < rate:
                    reported.append(m)
        return Evidence(sorted(reported), "oracle", True, None, 0.0, {}, True)
