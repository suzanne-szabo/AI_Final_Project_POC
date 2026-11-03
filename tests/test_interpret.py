"""Offline tests for the evidence interpreter, including the prompt-cache rules (architecture D8)."""

import importlib

from langchain_core.messages import AIMessage

from mm_agent import interpret as interp
from mm_agent.probes import BY_ID


class ScriptedModel:
    """Fake chat model: records what it was sent and returns scripted replies."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []
        self.bound_tools = []

    def bind_tools(self, tools, **kwargs):
        self.bound_tools.append((tools, kwargs))
        return self

    def invoke(self, messages):
        self.sent.append(messages)
        return self.replies.pop(0)


def call(name, args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "c1", "type": "tool_call"}])


def test_prefix_is_identical_across_cases_and_reloads():
    model = ScriptedModel([call(interp.TOOL_NAME, {"misconceptions": [], "rationale": "x"})] * 2)
    bound = interp.bind(model)
    interp.interpret(bound, BY_ID["P05"], "3 | None", "no return, so None")
    interp.interpret(bound, BY_ID["P12"], "after | 2", "keeps going after return")
    first, second = model.sent
    assert first[0].content == second[0].content  # system prompt identical
    assert first[1].content != second[1].content  # only the final user message varies
    assert len(first) == 2 and type(first[-1]).__name__ == "HumanMessage"
    before = (interp.SYSTEM_PROMPT, interp.tool_definition_bytes())
    importlib.reload(interp)  # a new process must build the same bytes
    assert (interp.SYSTEM_PROMPT, interp.tool_definition_bytes()) == before


def test_system_prompt_has_no_volatile_content():
    for marker in ("2026", "seed", "step", "Qwen", "Gemma"):
        assert marker not in interp.SYSTEM_PROMPT


def test_valid_call_is_parsed_and_sorted():
    model = ScriptedModel([call(interp.TOOL_NAME, {"misconceptions": ["F4_LOCALS_OUTLIVE_CALL", "F1_RETURN_IS_PRINT"],
                                                   "rationale": "says value still 3"})])
    ev = interp.interpret(interp.bind(model), BY_ID["P11"], "4 3", "...")
    assert ev.valid and ev.labels == ["F1_RETURN_IS_PRINT", "F4_LOCALS_OUTLIVE_CALL"]


def test_unknown_id_is_rejected():
    model = ScriptedModel([call(interp.TOOL_NAME, {"misconceptions": ["MADE_UP"], "rationale": "x"})])
    ev = interp.interpret(interp.bind(model), BY_ID["P05"], "3 | 3", "...")
    assert not ev.valid and "unknown" in ev.error


def test_plain_text_reply_is_invalid():
    model = ScriptedModel([AIMessage(content="The student has F1.")])
    ev = interp.interpret(interp.bind(model), BY_ID["P05"], "3 | 3", "...")
    assert not ev.valid


def test_model_exception_is_recorded_not_raised():
    class Broken(ScriptedModel):
        def invoke(self, messages):
            raise TimeoutError("gateway timeout")

    ev = interp.interpret(interp.bind(Broken([])), BY_ID["P05"], "3 | 3", "...")
    assert not ev.valid and ev.error.startswith("MODEL_ERROR")
