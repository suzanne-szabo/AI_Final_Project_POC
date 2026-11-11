"""Black-box tests for specs/agent.md §4 (prompts) and §5 (LangSmith tracing)."""

import importlib
import json
import random
from pathlib import Path

import pytest

from mm_agent import prompts
from mm_agent.catalog import CATALOG
from mm_agent.config import Config
from mm_agent.controller import Controller
from mm_agent.interpret import Evidence
from mm_agent.policies import run_policy_session
from mm_agent.probes import BANK
from mm_agent.session import Session
from mm_agent.students import BankStudent, ExplanationBank, Response, ScriptedStudent
from mm_agent.tracing import traceable, tracing_enabled

DATA = Path(__file__).resolve().parent.parent / "data"


class Interp:
    def label(self, probe, answer, explanation):
        return Evidence([], "", True, None, 0.0, {}, True)


def make(config=Config(), interpreter=Interp(), answer=None):
    responses = {p.id: Response(p.correct, 5) for p in BANK}
    if answer:
        responses["P07"] = answer
    s = Session.new(ScriptedStudent("s", responses, {}), interpreter, config, session_id="p", decider="interviewer")
    return s, Controller(s, "model")


def test_system_prompt_is_constant_and_complete():
    before = prompts.SYSTEM_PROMPT
    importlib.reload(prompts)
    assert prompts.SYSTEM_PROMPT == before
    for m in CATALOG:
        assert m.id in before and m.summary in before
    for tool in ("rank_probes", "ask_probe", "ask_explanation", "submit_diagnosis"):
        assert tool in before
    for volatile in ("Qwen", "Gemma", "2026", "Step "):
        assert volatile not in before
    assert prompts.OPENING == "Begin the session."


def test_status_message_basics():
    s, c = make(answer=Response("6", 1))
    c.begin_step()
    msg = prompts.status_message(s, c)
    assert "Step 1 of 30." in msg and "Probes used 0 of 10." in msg and "Explanations used 0 of 5." in msg
    assert "Belief confident: no." in msg
    c.handle("ask_probe", {"probe_id": "P07"})
    c.begin_step()
    msg = prompts.status_message(s, c)
    assert "F2_PARAM_LINKED 0.48" in msg and "Last probe: P07 (explanation available)." in msg


def test_status_message_budget_and_last_step():
    s, c = make(config=Config(max_probes=1))
    c.begin_step()
    c.handle("ask_probe", {"probe_id": "P07"})
    c.begin_step()
    assert "The probe budget is spent: call submit_diagnosis." in prompts.status_message(s, c)
    s2, c2 = make(config=Config(max_steps=1))
    c2.begin_step()
    assert "This is your last step" in prompts.status_message(s2, c2)


@pytest.mark.parametrize("value,expected", [(None, False), ("true", True), ("TRUE", True), ("1", True), ("false", False)])
def test_tracing_enabled(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    else:
        monkeypatch.setenv("LANGSMITH_TRACING", value)
    assert tracing_enabled() is expected


def test_traceable_does_not_change_results(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)

    @traceable(name="double")
    def double(x):
        return 2 * x

    assert double(21) == 42


def run_session():
    bank = ExplanationBank.load(DATA / "explanation_bank.jsonl")
    stu = BankStudent("s", frozenset({"A1_LINKED"}), 0.15, random.Random("t"), bank)
    return run_policy_session(stu, "eig", Config(), seed=1, session_id="s")


def test_tracing_off_or_false_gives_identical_sessions(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    a = run_session()
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    b = run_session()
    assert json.dumps(a.trace, sort_keys=True) == json.dumps(b.trace, sort_keys=True)
    assert a.trace[0]["tracing"]["langsmith"] is False
    assert "api_key" not in json.dumps(a.trace[0]).lower()


def test_explanation_guidance_is_explicit():
    """D30: ask after a misconception, unexpected or low-confidence answer; not after a confident correct one."""
    text = " ".join(prompts.SYSTEM_PROMPT.split())
    assert "Call ask_explanation right after an answer that matches a misconception" in text
    assert "Do not call ask_explanation after a correct answer given with confidence 3 or higher" in text
    assert "consider ask_explanation" not in text
