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
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ValidationError

from mm_agent.catalog import CATALOG, IDS
from mm_agent.probes import Probe

TOOL_NAME = "record_evidence"


class RecordEvidence(BaseModel):
    misconceptions: list[str] = Field(default_factory=list, max_length=3)
    rationale: str = Field(max_length=400)

    def checked(self) -> "RecordEvidence":
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
            },
            "required": ["misconceptions", "rationale"],
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
- Label only what the explanation shows. A wrong prediction with no explanation of why is weak \
evidence; label it only if the prediction matches a misconception's typical answer and nothing in \
the explanation contradicts it.
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
    return Evidence(sorted(evidence.misconceptions), evidence.rationale, True, None, seconds, usage)
