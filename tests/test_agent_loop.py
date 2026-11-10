"""Black-box tests for the LangGraph interviewer loop (specs/agent.md §3) with a scripted fake model."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from mm_agent.agent import run_interviewer_session
from mm_agent.config import Config
from mm_agent.interpret import Evidence
from mm_agent.probes import BANK
from mm_agent.prompts import OPENING, SYSTEM_PROMPT
from mm_agent.students import Response, ScriptedStudent
from mm_agent.tools import tool_definitions
from tests.fakes import ScriptedChatModel, reply, tool_call

F2 = "F2_PARAM_LINKED"
LOOSE = Config(low=0.25, high=0.75)


class FixedInterpreter:
    def __init__(self, labels):
        self.labels = labels

    def label(self, probe, answer, explanation):
        return Evidence(list(self.labels), "r", True, None, 0.0, {}, True)


def student():
    responses = {p.id: Response(p.correct, 5) for p in BANK}
    responses["P07"] = Response("6", 5)
    return ScriptedStudent("stu", responses, {p.id: f"because {p.id}" for p in BANK})


def run(script, config=LOOSE, interpreter=None):
    model = ScriptedChatModel(script)
    result = run_interviewer_session(student(), config, model, interpreter or FixedInterpreter([F2]),
                                     session_id="a1", seed=1)
    return model, result


def calls(result):
    return [r for r in result.trace if r["kind"] == "call"]


def events(result):
    return [r["event"] for r in result.trace if r["kind"] == "model"]


def test_full_session_ends_diagnosed():
    model, result = run([reply(tool_call("rank_probes", {"k": 3})),
                         reply(tool_call("ask_probe", {"probe_id": "P07"})),
                         reply(tool_call("ask_explanation")),
                         reply(tool_call("submit_diagnosis"))])
    assert result.terminal == "DIAGNOSED"
    assert result.steps_used == 4 and result.model_calls == 4
    assert result.probes_used == 1 and result.explanations_used == 1
    assert result.estimate["most_likely"] == [F2]
    assert [c["tool"] for c in calls(result)] == ["rank_probes", "ask_probe", "ask_explanation", "submit_diagnosis"]
    assert all(c["actor"] == "model" for c in calls(result))
    assert result.trace[0]["decider"] == "interviewer"


def test_prompt_layout_status_last_and_history_append_only():
    model, _ = run([reply(tool_call("rank_probes")), reply(tool_call("ask_probe", {"probe_id": "P07"})),
                    reply(tool_call("submit_diagnosis"))])
    first, second, third = model.sent
    for sent in model.sent:
        assert isinstance(sent[0], SystemMessage) and sent[0].content == SYSTEM_PROMPT
        assert isinstance(sent[1], HumanMessage) and sent[1].content == OPENING
        assert isinstance(sent[-1], HumanMessage) and sent[-1].content.startswith("Step ")
    assert second[:len(first) - 1] == first[:-1]
    assert third[:len(second) - 1] == second[:-1]
    assert first[-1] not in second[:-1]                 # the old status message is not stored
    assert isinstance(second[-3], AIMessage) and isinstance(second[-2], ToolMessage)


def test_model_is_bound_with_forced_single_tool_calls():
    model, _ = run([reply(tool_call("submit_diagnosis"))])
    tools, kwargs = model.bound[0]
    assert tools == tool_definitions()
    assert kwargs.get("tool_choice") == "required" and kwargs.get("parallel_tool_calls") is False


def test_every_tool_call_gets_exactly_one_tool_message_and_extra_calls_are_p8():
    model, result = run([reply(tool_call("rank_probes", call_id="c1"), tool_call("ask_probe", {"probe_id": "P07"}, "c2")),
                         reply(tool_call("submit_diagnosis", call_id="c3"))])
    last = model.sent[-1]
    asked = [tc["id"] for m in last if isinstance(m, AIMessage) for tc in m.tool_calls]
    answered = [m.tool_call_id for m in last if isinstance(m, ToolMessage)]
    assert asked == ["c1", "c2"] and answered == ["c1", "c2"]
    extra = [c for c in calls(result) if c["tool"] == "ask_probe"][0]
    assert extra["accepted"] is False and extra["policy"] == "P8"
    assert result.terminal == "DIAGNOSED"


def test_thoughts_are_recorded():
    _, result = run([reply(tool_call("submit_diagnosis"), text="The belief is already confident.")])
    assert "thought" in events(result)


def test_no_action_reminder_then_error():
    model, result = run([reply(text="Let me think."), reply(text="Still thinking.")])
    assert result.terminal == "ERROR" and result.error_kind == "NO_ACTION"
    assert "reminder" in events(result) and "no_action" in events(result)


def test_reminder_then_recovery():
    _, result = run([reply(text="hmm"), reply(tool_call("submit_diagnosis"))])
    assert result.terminal == "DIAGNOSED"


def test_model_error_after_one_retry():
    _, result = run([TimeoutError("gateway"), TimeoutError("gateway")])
    assert result.terminal == "ERROR" and result.error_kind == "MODEL_ERROR"
    _, recovered = run([TimeoutError("gateway"), reply(tool_call("submit_diagnosis"))])
    assert recovered.terminal == "DIAGNOSED"


def test_step_limit():
    _, result = run([reply(tool_call("rank_probes"))] * 3, config=Config(max_steps=3))
    assert result.terminal == "STEP_LIMIT" and result.steps_used == 3


def test_rejection_limit_in_the_loop():
    _, result = run([reply(tool_call("submit_diagnosis"))] * 3, config=Config())
    assert result.terminal == "ERROR" and result.error_kind == "REJECTION_LIMIT"
    assert all(c["policy"] == "P7" for c in calls(result))
