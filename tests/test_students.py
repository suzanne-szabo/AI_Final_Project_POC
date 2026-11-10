"""Black-box tests for specs/students.md (Student interface, BankStudent, ScriptedStudent, LLMStudent)."""

import random
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from mm_agent.catalog import BY_ID as CATALOG
from mm_agent.catalog import IDS
from mm_agent.probes import BANK, BY_ID, strip_hedges
from mm_agent.students import (CORRECT_BELIEFS, STUDENT_SYSTEM_PROMPT, BankStudent, ExplanationBank, LLMStudent,
                               Response, ScriptedStudent, SimStudent, beliefs_message, random_profile)
from tests.fakes import ScriptedChatModel, reply, tool_call

DATA = Path(__file__).resolve().parent.parent / "data"
BANKDATA = ExplanationBank.load(DATA / "explanation_bank.jsonl")
F2 = "F2_PARAM_LINKED"


def bank_student(profile=frozenset(), slip=0.0, seed=0, **kw):
    return BankStudent("s", frozenset(profile), slip, random.Random(seed), BANKDATA, **kw)


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_bank_student_without_extras_reproduces_week1_sim_student(seed):
    rng = random.Random(seed)
    profile = random_profile(rng, 0.4)
    sim = SimStudent("s", profile, 0.3, random.Random(f"{seed}-s"))
    bank = BankStudent("s", profile, 0.3, random.Random(f"{seed}-s"), BANKDATA,
                       confidence_mode="none", vague_answer_rate=0.0)
    for probe in BANK:
        r = bank.answer(probe)
        assert isinstance(r, Response) and r.confidence is None
        assert r.answer == sim.answer(probe)


def test_informative_confidence_tracks_slips():
    honest = bank_student(slip=0.0, vague_answer_rate=0.0)
    slipping = bank_student(slip=1.0, vague_answer_rate=0.0)
    for probe in BANK:
        r = honest.answer(probe)
        assert r.answer == probe.intended(frozenset()) and r.confidence in {3, 4, 5}
        s = slipping.answer(probe)
        assert s.answer != probe.intended(frozenset()) and s.confidence in {1, 2, 3}


def test_uninformative_and_none_modes():
    u = bank_student(slip=0.5, confidence_mode="uninformative", vague_answer_rate=0.0)
    assert {u.answer(p).confidence for p in BANK} <= {1, 2, 3, 4, 5}
    n = bank_student(confidence_mode="none", vague_answer_rate=0.0)
    assert all(n.answer(p).confidence is None for p in BANK)


def test_hedged_answers_use_the_templates_and_strip_back():
    s = bank_student(profile={F2}, vague_answer_rate=1.0)
    for probe in BANK:
        r = s.answer(probe)
        a = probe.intended(frozenset({F2}))
        assert r.answer in {f"maybe {a}?", f"I think {a}", f"{a}, not sure"}
        assert r.confidence in {1, 2}
        assert probe.classify(strip_hedges(r.answer)) == a


@pytest.mark.parametrize("text,expected", [("maybe 7 5?", "7 5"), ("6, not sure", "6"), ("I think [1, 2, 3]", "[1, 2, 3]"),
                                           ("probably 2 6", "2 6"), ("not sure", ""), ("i'm not sure, 42", "42")])
def test_strip_hedges(text, expected):
    assert strip_hedges(text) == expected


def test_explain_chooses_the_matching_bank_entry():
    p07 = BY_ID["P07"]
    holder = bank_student(profile={F2}, clarity_mix={"clear": 1.0}, vague_answer_rate=0.0)
    holder.answer(p07)
    texts = {e.text for e in BANKDATA.entries("P07", "misconception", F2, "clear")}
    assert holder.explain(p07) in texts
    correct = bank_student(clarity_mix={"vague": 1.0}, vague_answer_rate=0.0)
    correct.answer(p07)
    assert correct.explain(p07) in {e.text for e in BANKDATA.entries("P07", "correct", clarity="vague")}
    slipper = bank_student(slip=1.0, clarity_mix={"clear": 1.0}, vague_answer_rate=0.0)
    slipper.answer(p07)
    assert slipper.explain(p07) in {e.text for e in BANKDATA.entries("P07", "slip")}
    silent = bank_student(profile={F2}, clarity_mix={"none": 1.0}, vague_answer_rate=0.0)
    silent.answer(p07)
    assert silent.explain(p07) in {e.text for e in BANKDATA.entries("P07", "none")}


def test_explain_before_answer_is_an_error():
    with pytest.raises(ValueError):
        bank_student().explain(BY_ID["P07"])


def test_scripted_student():
    s = ScriptedStudent("x", {"P07": Response("6", 5)}, {"P07": "n is x"})
    assert s.answer(BY_ID["P07"]) == Response("6", 5)
    assert s.explain(BY_ID["P07"]) == "n is x"
    with pytest.raises(KeyError):
        s.answer(BY_ID["P01"])


def test_correct_beliefs_and_beliefs_message():
    assert set(CORRECT_BELIEFS) == set(IDS)
    msg = beliefs_message(frozenset({F2}))
    assert CATALOG[F2].summary in msg
    assert CORRECT_BELIEFS[F2] not in msg
    for m in IDS:
        if m != F2:
            assert CORRECT_BELIEFS[m] in msg


def test_llm_student_prompt_structure_and_append_only_history():
    model = ScriptedChatModel([reply(tool_call("respond", {"answer": "6", "confidence": 4})),
                               reply(tool_call("explain", {"text": "n is x so x goes up"}))])
    s = LLMStudent("llm-1", frozenset({F2}), model)
    assert s.answer(BY_ID["P07"]) == Response("6", 4)
    assert s.explain(BY_ID["P07"]) == "n is x so x goes up"
    first, second = model.sent
    assert isinstance(first[0], SystemMessage) and first[0].content == STUDENT_SYSTEM_PROMPT
    assert isinstance(first[1], HumanMessage) and first[1].content == beliefs_message(frozenset({F2}))
    assert second[:len(first)] == first
    assert any(isinstance(m, AIMessage) for m in second) and any(isinstance(m, ToolMessage) for m in second)
    tools, kwargs = model.bound[0]
    assert kwargs.get("tool_choice") == "required" and kwargs.get("parallel_tool_calls") is False
    assert {t["function"]["name"] if "function" in t else t["name"] for t in tools} == {"respond", "explain"}


def test_llm_students_share_the_system_prompt():
    a = ScriptedChatModel([reply(tool_call("respond", {"answer": "5", "confidence": 3}))])
    b = ScriptedChatModel([reply(tool_call("respond", {"answer": "6", "confidence": 3}))])
    LLMStudent("a", frozenset(), a).answer(BY_ID["P07"])
    LLMStudent("b", frozenset({F2}), b).answer(BY_ID["P07"])
    assert a.sent[0][0].content == b.sent[0][0].content


def test_llm_student_retries_then_falls_back():
    ok = ScriptedChatModel([reply(), reply(tool_call("respond", {"answer": "5", "confidence": 2}))])
    s = LLMStudent("a", frozenset(), ok, max_retries=1)
    assert s.answer(BY_ID["P07"]) == Response("5", 2) and s.failures == 0
    bad = ScriptedChatModel([reply(tool_call("respond", {"answer": "5", "confidence": 9})), reply()])
    t = LLMStudent("b", frozenset(), bad, max_retries=1)
    assert t.answer(BY_ID["P07"]) == Response("something unexpected", None) and t.failures == 1
    explains_badly = ScriptedChatModel([reply(tool_call("respond", {"answer": "5", "confidence": 2})), reply(), reply()])
    u = LLMStudent("c", frozenset(), explains_badly, max_retries=1)
    u.answer(BY_ID["P07"])
    assert u.explain(BY_ID["P07"]) == "I'm not sure." and u.failures == 1
    with pytest.raises(ValueError):
        LLMStudent("d", frozenset(), ScriptedChatModel([])).explain(BY_ID["P07"])
