"""The eight interviewer-check scenarios (specs/agent.md §7, D16), built offline.

Each scenario replays a fixed sequence of interviewer actions through a real `Controller` (actor
"model") with a `ScriptedStudent`, storing the same AI and tool messages the LangGraph loop would store,
then begins the next step and builds the exact message list the interviewer would be sent (system
prompt, opening, stored history, status message). `scripts/check_interviewer.py` makes one live model
call per scenario and lets the scenario's controller validate (not execute) the reply.

`Scenario.expected(tool_name, accepted) -> bool` says whether a reply is the expected action.
`state_problems(scenario)` re-checks that a scenario is in its stated state (the script calls it before
spending a model call).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage

from mm_agent.agent import build_request, tool_message
from mm_agent.config import Config
from mm_agent.controller import Controller
from mm_agent.interpret import Evidence
from mm_agent.probes import BANK
from mm_agent.select import rank_probes
from mm_agent.session import Session
from mm_agent.students import Response, ScriptedStudent

F2 = "F2_PARAM_LINKED"


@dataclass
class Scenario:
    name: str
    session: Session
    controller: Controller
    messages: list
    expected: Callable[[str, bool], bool]
    situation: str = ""
    expected_text: str = ""
    top_probe: str | None = field(default=None)  # the top-ranked unasked probe when the model is called


class _ScriptedInterpreter:
    """Labels each scripted explanation with fixed evidence (no network)."""

    def __init__(self, table: dict[str, Evidence]):
        self.table = table

    def label(self, probe, answer, explanation):
        return self.table.get(explanation, Evidence([], "scripted", True, None, 0.0, {}, False))


def _student(**answers: Response) -> ScriptedStudent:
    responses = {p.id: Response(p.correct, 5) for p in BANK}
    responses.update(answers)
    explanations = {p.id: f"I traced {p.id} line by line." for p in BANK}
    explanations["P07"] = "n is x, so when n goes up x goes up too."
    return ScriptedStudent("check", responses, explanations)


_INTERPRETER = _ScriptedInterpreter({
    "n is x, so when n goes up x goes up too.": Evidence([F2], "scripted", True, None, 0.0, {}, True),
})


def _replay(name: str, actions: list[tuple[str, dict]], student: ScriptedStudent, config: Config) -> tuple:
    session = Session.new(student, _INTERPRETER, config, session_id=f"check-{name}", decider="interviewer",
                          seed=0)
    controller = Controller(session, "model")
    history: list = []
    for number, (tool, args) in enumerate(actions, start=1):
        controller.begin_step()
        call_id = f"{name}-call-{number}"
        history.append(AIMessage(content="", tool_calls=[{"name": tool, "args": args, "id": call_id,
                                                          "type": "tool_call"}]))
        history.append(tool_message(controller.handle(tool, args), call_id))
        if controller.check_terminal() is not None:
            raise RuntimeError(f"scenario {name} ended while replaying")
    controller.begin_step()  # the step the interviewer is about to take
    unasked = session.unasked()
    top = rank_probes(session.belief, unasked)[0][0].id if unasked else None
    return session, controller, build_request(session, controller, history), top


def _confident_actions(config: Config) -> list[tuple[str, dict]]:
    """rank_probes, then the top-ranked probe answered correctly with confidence 5, until confident."""
    session = Session.new(_student(), None, config, session_id="plan", decider="plan")
    probe_controller = Controller(session, "policy")
    actions: list[tuple[str, dict]] = [("rank_probes", {})]
    while not session.belief.is_confident(config.low, config.high):
        probe_id = rank_probes(session.belief, session.unasked())[0][0].id
        probe_controller.handle("ask_probe", {"probe_id": probe_id})
        actions.append(("ask_probe", {"probe_id": probe_id}))
    return actions


def _probing(tool: str, accepted: bool) -> bool:
    return accepted and tool in ("rank_probes", "ask_probe")


def build_scenarios() -> list[Scenario]:
    """S1-S8 in order, each freshly replayed (a scenario's controller is used for one validation)."""
    default = Config()
    specs = [
        ("S1", "Session start", "rank_probes, or ask_probe with the top-ranked probe",
         [], _student(), default, _probing),
        ("S2", "Last answer matches a misconception, confidence 5", "ask_explanation",
         [("rank_probes", {}), ("ask_probe", {"probe_id": "P07"})], _student(P07=Response("6", 5)), default,
         lambda tool, ok: ok and tool == "ask_explanation"),
        ("S3", "Last answer was unexpected", "ask_explanation",
         [("rank_probes", {}), ("ask_probe", {"probe_id": "P07"})], _student(P07=Response("12", 3)), default,
         lambda tool, ok: ok and tool == "ask_explanation"),
        ("S4", "Belief confident", "submit_diagnosis",
         _confident_actions(default), _student(), default,
         lambda tool, ok: ok and tool == "submit_diagnosis"),
        ("S5", "Two probes asked, not confident", "anything except submit_diagnosis",
         [("rank_probes", {}), ("ask_probe", {"probe_id": "P07"}), ("ask_probe", {"probe_id": "P01"})],
         _student(P07=Response("6", 2), P01=Response("7 5", 3)), default,
         lambda tool, ok: ok and tool != "submit_diagnosis"),
        ("S6", "Probe budget spent (max_probes=3)", "submit_diagnosis",
         [("rank_probes", {}), ("ask_probe", {"probe_id": "P07"}), ("ask_probe", {"probe_id": "P01"}),
          ("ask_probe", {"probe_id": "P10"})],
         _student(P07=Response("6", 2), P01=Response("7 7", 2), P10=Response("42", 1)), Config(max_probes=3),
         lambda tool, ok: ok and tool == "submit_diagnosis"),
        ("S7", "Last answer correct, confidence 5", "rank_probes or ask_probe",
         [("rank_probes", {}), ("ask_probe", {"probe_id": "P07"})], _student(), default, _probing),
        ("S8", "Previous call was rejected (probe already asked)", "an accepted call",
         [("rank_probes", {}), ("ask_probe", {"probe_id": "P07"}), ("ask_probe", {"probe_id": "P07"})],
         _student(P07=Response("5", 4)), default,
         lambda tool, ok: ok),
    ]
    scenarios = []
    for name, situation, expected_text, actions, student, config, expected in specs:
        session, controller, messages, top = _replay(name, actions, student, config)
        scenarios.append(Scenario(name, session, controller, messages, expected, situation, expected_text, top))
    return scenarios


def state_problems(scenario: Scenario) -> list[str]:
    """Differences between a scenario's replayed state and its stated situation ([] when as stated)."""
    s, c = scenario.session, scenario.controller
    confident = s.belief.is_confident(s.config.low, s.config.high)
    calls = [r for r in c.trace if r["kind"] == "call"]
    last = calls[-1] if calls else None
    problems = []
    data = (last or {}).get("data") or {}
    matches, rated = data.get("answer_matches"), data.get("confidence")
    checks = {
        "S1": lambda: not s.asked,
        "S2": lambda: matches not in (None, ["correct"], ["unexpected"]) and rated == 5 and not confident,
        "S3": lambda: matches == ["unexpected"] and not confident,
        "S4": lambda: confident and s.probes_remaining() > 0,
        "S5": lambda: len(s.asked) == 2 and not confident,
        "S6": lambda: s.config.max_probes == 3 and len(s.asked) == 3 and s.probes_remaining() == 0,
        "S7": lambda: matches == ["correct"] and rated == 5 and not confident,
        "S8": lambda: last is not None and last["accepted"] is False and last.get("policy") == "P4",
    }
    if scenario.name not in checks or not checks[scenario.name]():
        problems.append(f"{scenario.name} is not in its stated state: {scenario.situation}")
    if c.terminal is not None:
        problems.append(f"{scenario.name} already has a terminal reason")
    return problems


__all__ = ["Scenario", "build_scenarios", "state_problems"]
