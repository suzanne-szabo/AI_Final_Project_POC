"""Black-box tests for the Interpreter protocol: the informative flag (D23), LLMInterpreter, OracleInterpreter."""

import random
from pathlib import Path

import pytest

from mm_agent import interpret as interp
from mm_agent.interpret import Evidence, LLMInterpreter, OracleInterpreter
from mm_agent.probes import BY_ID
from mm_agent.students import ExplanationBank
from tests.fakes import ScriptedChatModel, reply, tool_call

DATA = Path(__file__).resolve().parent.parent / "data"
BANK = ExplanationBank.load(DATA / "explanation_bank.jsonl")
F2 = "F2_PARAM_LINKED"


def test_tool_requires_informative():
    params = interp.TOOL["function"]["parameters"]
    assert params["properties"]["informative"]["type"] == "boolean"
    assert "informative" in params["required"]


def test_prompt_has_the_informative_rules_and_not_the_old_rule():
    assert "informative" in interp.SYSTEM_PROMPT
    assert "weak evidence" not in interp.SYSTEM_PROMPT


def test_evidence_defaults_to_informative():
    assert Evidence([], "", True, None, 0.0, {}).informative is True


def test_non_informative_reply_is_valid_and_has_no_labels():
    model = ScriptedChatModel([reply(tool_call(interp.TOOL_NAME, {"misconceptions": [], "rationale": "idk",
                                                                  "informative": False}))])
    ev = LLMInterpreter(model).label(BY_ID["P07"], "6", "idk")
    assert ev.valid and ev.informative is False and ev.labels == []


def test_non_informative_with_labels_is_invalid():
    model = ScriptedChatModel([reply(tool_call(interp.TOOL_NAME, {"misconceptions": [F2], "rationale": "x",
                                                                  "informative": False}))])
    assert not LLMInterpreter(model).label(BY_ID["P07"], "6", "idk").valid


def test_llm_interpreter_binds_once():
    model = ScriptedChatModel([reply(tool_call(interp.TOOL_NAME, {"misconceptions": [F2], "rationale": "x",
                                                                  "informative": True}))] * 2)
    li = LLMInterpreter(model)
    li.label(BY_ID["P07"], "6", "a")
    li.label(BY_ID["P15"], "6 6", "b")
    assert len(model.bound) == 1
    assert model.sent[0][0].content == model.sent[1][0].content


def entry(probe_id, kind, clarity, misconception=None):
    return BANK.entries(probe_id, kind, misconception, clarity)[0]


def test_oracle_unknown_text_is_invalid():
    ev = OracleInterpreter(BANK, 0.85, 0.05, random.Random(0)).label(BY_ID["P07"], "6", "not in bank")
    assert not ev.valid


def test_oracle_non_informative_entry():
    e = entry("P07", "none", "none")
    ev = OracleInterpreter(BANK, 0.85, 0.05, random.Random(0)).label(BY_ID["P07"], "6", e.text)
    assert ev.valid and ev.informative is False and ev.labels == []


def test_oracle_rates_match_configuration():
    e = entry("P07", "misconception", "clear", F2)
    c = entry("P07", "correct", "clear")
    oracle = OracleInterpreter(BANK, 0.85, 0.05, random.Random(123))
    hits = sum(F2 in oracle.label(BY_ID["P07"], "6", e.text).labels for _ in range(4000))
    alarms = sum(F2 in oracle.label(BY_ID["P07"], "5", c.text).labels for _ in range(4000))
    assert hits / 4000 == pytest.approx(0.85, abs=0.03)
    assert alarms / 4000 == pytest.approx(0.05, abs=0.02)


def test_oracle_is_deterministic_for_a_seed():
    e = entry("P01", "misconception", "vague", "A1_LINKED")
    a = OracleInterpreter(BANK, 0.85, 0.05, random.Random(5))
    b = OracleInterpreter(BANK, 0.85, 0.05, random.Random(5))
    assert [a.label(BY_ID["P01"], "7 7", e.text).labels for _ in range(50)] == \
           [b.label(BY_ID["P01"], "7 7", e.text).labels for _ in range(50)]
