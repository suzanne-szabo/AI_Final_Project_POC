"""Black-box tests for the LLM-student fidelity check (mm_agent/fidelity.py, D35)."""

from mm_agent.fidelity import DEFAULT_PROFILES, run_student, score_answer, summarize
from mm_agent.probes import BANK, BY_ID
from mm_agent.students import LLMStudent
from tests.fakes import ScriptedChatModel, reply, tool_call

F2, A3 = "F2_PARAM_LINKED", "A3_COPY_ON_ASSIGN"


def test_default_profiles_cover_every_misconception_and_none():
    held = set().union(*DEFAULT_PROFILES)
    assert frozenset() in DEFAULT_PROFILES and len(held) == 8
    assert len(DEFAULT_PROFILES) == len(set(DEFAULT_PROFILES))


def test_outcomes_on_belief_and_neutral_probes():
    p07, p01 = BY_ID["P07"], BY_ID["P01"]
    assert score_answer("s", frozenset({F2}), None, p07, "6", 4).outcome == "faithful"
    assert score_answer("s", frozenset({F2}), None, p07, "5", 4).outcome == "leak"
    assert score_answer("s", frozenset({F2}), None, p07, "maybe 6?", 2).outcome == "faithful"   # hedges stripped
    assert score_answer("s", frozenset({F2}), None, p07, "banana", 1).outcome == "unexpected"
    neutral = score_answer("s", frozenset({F2}), None, p01, "7 7", 3)
    assert not neutral.belief_probe and neutral.outcome == "invented"
    assert score_answer("s", frozenset(), None, p01, "7 5", 5).outcome == "faithful"
    assert score_answer("s", frozenset({F2}), None, p07, "6", 4).misconception == F2


def test_summary_rates():
    rows = [score_answer("s", frozenset({F2}), None, BY_ID["P07"], "6", 5),
            score_answer("s", frozenset({F2}), None, BY_ID["P15"], "2 6", 4),   # leak
            score_answer("s", frozenset({F2}), None, BY_ID["P01"], "7 5", 5)]   # neutral, correct
    s = summarize(rows)
    assert (s["belief_answers"], s["neutral_answers"]) == (2, 1)
    assert s["belief_fidelity"] == 0.5 and s["leak_rate"] == 0.5 and s["neutral_accuracy"] == 1.0
    assert s["per_misconception"][F2]["fidelity"] == 0.5
    assert s["mean_confidence_leak"] == 4


def test_run_student_asks_every_probe_and_explains_only_belief_probes():
    profile = frozenset({A3})
    replies = []
    for probe in BANK:
        replies.append(reply(tool_call("respond", {"answer": probe.intended(profile), "confidence": 4})))
        if probe.intended(profile) != probe.correct:
            replies.append(reply(tool_call("explain", {"text": "b is its own copy"})))
    student = LLMStudent("llm-a3", profile, ScriptedChatModel(replies), style="clear")
    scored, explanations = run_student(student, explain=True)
    assert len(scored) == 15 and all(r.outcome == "faithful" for r in scored)
    assert set(explanations) == {"P03", "P14"} and student.failures == 0
    assert all(r.style == "clear" for r in scored)
