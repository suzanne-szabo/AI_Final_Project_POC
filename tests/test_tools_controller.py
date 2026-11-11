"""Black-box tests for specs/tools.md and specs/controller.md."""

import json

import pytest

from mm_agent.config import Config
from mm_agent.controller import Controller, Observation
from mm_agent.interpret import Evidence
from mm_agent.probes import BANK
from mm_agent.session import Session
from mm_agent.students import Response, ScriptedStudent
from mm_agent.tools import SCHEMAS, tool_definitions

F2 = "F2_PARAM_LINKED"
A1 = "A1_LINKED"
LOOSE = Config(low=0.25, high=0.75)      # the prior (0.2) already counts as confident


class FixedInterpreter:
    def __init__(self, evidence):
        self.evidence, self.calls = evidence, []

    def label(self, probe, answer, explanation):
        self.calls.append((probe.id, answer, explanation))
        return self.evidence


def ev(labels=(), valid=True, informative=True):
    return Evidence(list(labels), "r", valid, None if valid else "boom", 0.0, {}, informative)


def student(**overrides):
    responses = {p.id: Response(p.correct, 5) for p in BANK}
    responses.update(overrides)
    s = ScriptedStudent("stu", responses, {p.id: f"because {p.id}" for p in BANK})
    return s


def make(stu=None, interpreter=None, config=None, actor="policy"):
    session = Session.new(stu or student(), interpreter, config or Config(), session_id="t1",
                          decider="test", models={"interviewer": None, "interpreter": None, "student": None})
    return session, Controller(session, actor)


def state(session):
    return (list(session.belief.weights), list(session.asked), set(session.explained))


# --- tools -------------------------------------------------------------------------------------

def test_tool_definitions_are_fixed_and_deterministic():
    defs = tool_definitions()
    assert [d["function"]["name"] for d in defs] == ["rank_probes", "ask_probe", "ask_explanation", "submit_diagnosis"]
    assert json.dumps(defs) == json.dumps(tool_definitions())
    assert set(SCHEMAS) == {"rank_probes", "ask_probe", "ask_explanation", "submit_diagnosis"}


def test_rank_probes():
    session, c = make()
    obs = c.handle("rank_probes", {"k": 4})
    assert obs.accepted
    ranked = obs.data["ranked"]
    assert len(ranked) == 4
    gains = [r["expected_gain"] for r in ranked]
    assert gains == sorted(gains, reverse=True)
    assert all(r["targets"] == sorted(r["targets"]) for r in ranked)
    assert obs.data["probes_used"] == 0 and obs.data["probes_remaining"] == 10 and obs.data["confident"] is False
    assert c.handle("rank_probes", {}).data["ranked"].__len__() == Config().rank_k


@pytest.mark.parametrize("given,matches", [(Response("6", 5), [F2]), (Response("5", 5), ["correct"]),
                                           (Response("banana", 2), ["unexpected"]), (Response("maybe 6?", 1), [F2])])
def test_ask_probe(given, matches):
    session, c = make(student(P07=given))
    obs = c.handle("ask_probe", {"probe_id": "P07"})
    assert obs.accepted
    d = obs.data
    assert d["probe_id"] == "P07" and d["answer"] == given.answer and d["confidence"] == given.confidence
    assert d["answer_matches"] == matches and "code" in d and d["probes_remaining"] == 9
    assert session.asked == ["P07"] and session.last_probe == "P07"


def test_confidence_is_used_only_when_configured():
    s1, c1 = make(student(P07=Response("6", 5)))
    s2, c2 = make(student(P07=Response("6", 5)), config=Config(use_confidence=False))
    c1.handle("ask_probe", {"probe_id": "P07"})
    c2.handle("ask_probe", {"probe_id": "P07"})
    assert s1.belief.marginals()[F2] == pytest.approx(0.92, abs=0.01)
    assert s2.belief.marginals()[F2] == pytest.approx(0.82, abs=0.01)


def test_ask_explanation_applies_relevant_labels_only():
    interp = FixedInterpreter(ev([F2, A1]))
    session, c = make(student(P07=Response("6", 5)), interp)
    c.handle("ask_probe", {"probe_id": "P07"})
    before = session.belief.marginals()[F2]
    obs = c.handle("ask_explanation", {})
    assert obs.accepted
    d = obs.data
    assert d["applied_labels"] == [F2] and d["ignored_labels"] == [A1] and d["belief_updated"] is True
    assert d["informative"] is True and d["explanation"] == "because P07"
    assert session.belief.marginals()[F2] > before
    assert interp.calls == [("P07", "6", "because P07")]


@pytest.mark.parametrize("evidence", [ev([], informative=False), ev([F2], valid=False)])
def test_uninformative_or_failed_explanation_leaves_belief_unchanged(evidence):
    session, c = make(student(P07=Response("6", 5)), FixedInterpreter(evidence))
    c.handle("ask_probe", {"probe_id": "P07"})
    before = list(session.belief.weights)
    obs = c.handle("ask_explanation", {})
    assert obs.accepted and obs.data["belief_updated"] is False
    assert session.belief.weights == before
    if not evidence.valid:
        assert "interpreter_error" in obs.data


# --- policies ----------------------------------------------------------------------------------

def assert_rejected(c, session, tool, args, policy):
    before = state(session)
    obs = c.handle(tool, args)
    assert not obs.accepted and obs.policy == policy, (tool, args, obs)
    assert state(session) == before
    return obs


def test_p2_unknown_tool():
    session, c = make()
    assert_rejected(c, session, "teach", {}, "P2")


@pytest.mark.parametrize("tool,args", [("ask_probe", {"probe_id": "P99"}), ("ask_probe", {"probe_id": "P07", "x": 1}),
                                       ("ask_probe", {}), ("rank_probes", {"k": 0}), ("rank_probes", {"k": 9}),
                                       ("submit_diagnosis", {"now": True})])
def test_p3_bad_arguments(tool, args):
    session, c = make()
    assert_rejected(c, session, tool, args, "P3")


def test_p4_probe_already_asked():
    session, c = make()
    c.handle("ask_probe", {"probe_id": "P07"})
    assert_rejected(c, session, "ask_probe", {"probe_id": "P07"}, "P4")


def test_p5_probe_budget():
    session, c = make(config=Config(max_probes=1))
    c.handle("ask_probe", {"probe_id": "P07"})
    obs = assert_rejected(c, session, "ask_probe", {"probe_id": "P01"}, "P5")
    assert "submit_diagnosis" in obs.message


def test_p6_explanation_rules():
    session, c = make(interpreter=FixedInterpreter(ev()), config=Config(max_explanations=1))
    assert_rejected(c, session, "ask_explanation", {}, "P6")            # no probe yet
    c.handle("ask_probe", {"probe_id": "P07"})
    assert c.handle("ask_explanation", {}).accepted
    assert_rejected(c, session, "ask_explanation", {}, "P6")            # already explained
    c.handle("ask_probe", {"probe_id": "P01"})
    assert_rejected(c, session, "ask_explanation", {}, "P6")            # budget spent
    s2, c2 = make(interpreter=None)
    c2.handle("ask_probe", {"probe_id": "P07"})
    assert_rejected(c2, s2, "ask_explanation", {}, "P6")                # no interpreter


def test_p7_submit_before_confident():
    session, c = make()
    obs = assert_rejected(c, session, "submit_diagnosis", {}, "P7")
    assert "10" in obs.message or "probes remain" in obs.message


def test_diagnosed_and_budget_terminals():
    session, c = make(config=LOOSE)
    assert c.handle("submit_diagnosis", {}).accepted
    t = c.check_terminal()
    assert t.reason == "DIAGNOSED" and t.error_kind is None
    assert session.estimate is not None
    s2, c2 = make(config=Config(max_probes=1))
    c2.handle("ask_probe", {"probe_id": "P07"})
    assert c2.handle("submit_diagnosis", {}).accepted
    assert c2.check_terminal().reason == "BUDGET"


def test_p1_after_terminal():
    session, c = make(config=LOOSE)
    c.handle("submit_diagnosis", {})
    c.check_terminal()
    assert_rejected(c, session, "rank_probes", {}, "P1")


def test_p8_extra_calls_do_not_count_toward_the_rejection_limit():
    session, c = make(actor="model")
    obs = c.reject_extra_call("rank_probes", {})
    assert not obs.accepted and obs.policy == "P8"
    assert c.consecutive_rejections == 0


def test_rejection_limit():
    session, c = make(actor="model")
    for _ in range(2):
        c.begin_step()
        c.handle("teach", {})
        assert c.check_terminal() is None
    c.begin_step()
    c.handle("rank_probes", {})                      # accepted: resets the count
    assert c.consecutive_rejections == 0
    for _ in range(3):
        c.begin_step()
        c.handle("teach", {})
    t = c.check_terminal()
    assert t.reason == "ERROR" and t.error_kind == "REJECTION_LIMIT"


def test_no_action_gets_one_reminder():
    session, c = make(actor="model")
    c.begin_step()
    reminder = c.record_no_action()
    assert reminder is not None and c.check_terminal() is None and c.consecutive_rejections == 1
    c.begin_step()
    assert c.record_no_action() is None
    t = c.check_terminal()
    assert t.reason == "ERROR" and t.error_kind == "NO_ACTION"


def test_model_error_is_terminal():
    session, c = make(actor="model")
    c.begin_step()
    c.record_model_error(TimeoutError("gateway"))
    t = c.check_terminal()
    assert t.reason == "ERROR" and t.error_kind == "MODEL_ERROR"


def test_step_limit_and_submit_on_last_step_counts():
    session, c = make(config=Config(max_steps=2), actor="model")
    c.begin_step()
    c.handle("rank_probes", {})
    assert c.check_terminal() is None
    c.begin_step()
    c.handle("rank_probes", {})
    assert c.check_terminal().reason == "STEP_LIMIT"
    s2, c2 = make(config=Config(max_steps=1, low=0.25, high=0.75), actor="model")
    c2.begin_step()
    c2.handle("submit_diagnosis", {})
    assert c2.check_terminal().reason == "DIAGNOSED"


# --- observations, trace, result -----------------------------------------------------------------

def test_observation_shape():
    ok = Observation("rank_probes", True, "fine", {"a": 1})
    assert ok.as_dict() == {"tool": "rank_probes", "accepted": True, "message": "fine", "data": {"a": 1}}
    bad = Observation("ask_probe", False, "no", {}, "P4")
    assert bad.as_dict()["policy"] == "P4"
    assert bad.to_json() == json.dumps(bad.as_dict(), sort_keys=True)


def test_trace_and_result():
    stu = student(P07=Response("6", 5))
    session, c = make(stu, FixedInterpreter(ev([F2])), config=Config(max_probes=2))
    c.handle("ask_probe", {"probe_id": "P07"})
    c.handle("ask_explanation", {})
    c.handle("ask_probe", {"probe_id": "P01"})
    c.handle("submit_diagnosis", {})
    c.check_terminal()
    result = c.result()
    trace = result.trace
    assert trace[0]["kind"] == "header" and trace[-1]["kind"] == "result"
    assert [r["seq"] for r in trace] == list(range(1, len(trace) + 1))
    head = trace[0]
    assert head["session_id"] == "t1" and head["decider"] == "test" and head["planted"] == []
    assert set(head["config"]) >= {"max_probes", "slip_by_confidence", "interpreter_sensitivity"}
    calls = [r for r in trace if r["kind"] == "call"]
    assert [r["tool"] for r in calls] == ["ask_probe", "ask_explanation", "ask_probe", "submit_diagnosis"]
    assert {"step", "actor", "args", "accepted", "message", "data", "probes_used", "explanations_used",
            "steps_used"} <= set(calls[0])
    assert sum(r["kind"] == "belief" for r in trace) == 3
    assert result.terminal == "BUDGET" and result.probes_used == 2 and result.explanations_used == 1
    assert result.estimate is not None and result.exact_match == (set(result.estimate["most_likely"]) == set())
    json.dumps(trace, sort_keys=True)


def test_explanation_scope_follows_the_matched_answer():
    """D27: an answer matching A1's key on P01 scores only A1; a correct answer scores A1 and A2."""
    s1, c1 = make(student(P01=Response("7 7", 5)), FixedInterpreter(ev([A1])))
    c1.handle("ask_probe", {"probe_id": "P01"})
    a2_before = s1.belief.marginals()["A2_REVERSED"]
    d = c1.handle("ask_explanation", {}).data
    assert d["scored"] == [A1] and d["applied_labels"] == [A1]
    assert s1.belief.marginals()["A2_REVERSED"] == pytest.approx(a2_before)
    s2, c2 = make(student(), FixedInterpreter(ev([])))
    c2.handle("ask_probe", {"probe_id": "P01"})
    a2 = s2.belief.marginals()["A2_REVERSED"]
    d2 = c2.handle("ask_explanation", {}).data
    assert d2["scored"] == ["A1_LINKED", "A2_REVERSED"]
    assert s2.belief.marginals()["A2_REVERSED"] < a2


def test_off_scope_labels_are_ignored_not_applied():
    s, c = make(student(P01=Response("7 7", 5)), FixedInterpreter(ev([A1, "A2_REVERSED"])))
    c.handle("ask_probe", {"probe_id": "P01"})
    d = c.handle("ask_explanation", {}).data
    assert d["applied_labels"] == [A1] and d["ignored_labels"] == ["A2_REVERSED"]
