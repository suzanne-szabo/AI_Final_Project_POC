"""Black-box tests for the code deciders (specs/agent.md §2), including the week-1 regression."""

import json
import random
from pathlib import Path

import pytest

from mm_agent.config import Config
from mm_agent.interpret import OracleInterpreter
from mm_agent.poc import SessionConfig, diagnose
from mm_agent.policies import run_policy_session
from mm_agent.probes import BANK
from mm_agent.students import BankStudent, ExplanationBank, SimStudent, random_profile

DATA = Path(__file__).resolve().parent.parent / "data"
EXPL = ExplanationBank.load(DATA / "explanation_bank.jsonl")


def students(seed, n, rate=0.2):
    rng = random.Random(seed)
    return [(f"sim-{i:03d}", random_profile(rng, rate)) for i in range(n)]


def bank_student(sid, profile, seed, slip=0.15, **kw):
    return BankStudent(sid, profile, slip, random.Random(f"{seed}-{sid}"), EXPL, **kw)


def calls(result):
    return [r for r in result.trace if r["kind"] == "call"]


def test_eig_reproduces_the_week1_proof_of_concept():
    config = Config(use_confidence=False)
    for sid, profile in students(7, 100):
        old = diagnose(SimStudent(sid, profile, 0.15, random.Random(f"7-{sid}")), "eig", SessionConfig(max_probes=10))
        new = run_policy_session(bank_student(sid, profile, 7, confidence_mode="none", vague_answer_rate=0.0),
                                 "eig", config, seed=7, session_id=sid)
        assert set(new.estimate["most_likely"]) == set(old.diagnosis), sid
        assert new.probes_used == old.probes_used, sid


def test_fixed_order_and_stop_rule():
    r = run_policy_session(bank_student("s", frozenset(), 1, slip=0.0), "fixed", Config(), seed=1)
    asked = [c["args"]["probe_id"] for c in calls(r) if c["tool"] == "ask_probe"]
    assert asked == [p.id for p in BANK][:len(asked)]
    assert calls(r)[-1]["tool"] == "submit_diagnosis" and calls(r)[-1]["accepted"]
    assert r.terminal in {"DIAGNOSED", "BUDGET"} and r.probes_used <= 10


def test_shuffled_is_deterministic_and_not_bank_order():
    def order(seed):
        r = run_policy_session(bank_student("s", frozenset(), seed, slip=0.0), "shuffled", Config(max_probes=10), seed=seed)
        return [c["args"]["probe_id"] for c in calls(r) if c["tool"] == "ask_probe"]
    assert order(3) == order(3)
    assert any(order(s) != [p.id for p in BANK][:len(order(s))] for s in range(5))


def test_eig_explain_asks_after_non_correct_answers_only():
    config = Config()
    for sid, profile in students(11, 20, rate=0.4):
        oracle = OracleInterpreter(EXPL, 0.85, 0.05, random.Random(f"11-{sid}-oracle"))
        r = run_policy_session(bank_student(sid, profile, 11), "eig_explain", config, interpreter=oracle, seed=11)
        cs = calls(r)
        for i, c in enumerate(cs):
            if c["tool"] == "ask_explanation":
                prev = cs[i - 1]
                assert prev["tool"] == "ask_probe" and prev["data"]["answer_matches"] != ["correct"]
        assert r.explanations_used <= config.max_explanations
        assert all(c["accepted"] for c in cs)


@pytest.mark.parametrize("decider", ["fixed", "shuffled", "eig"])
def test_policies_never_get_rejected_and_are_deterministic(decider):
    def run():
        r = run_policy_session(bank_student("s", frozenset({"F2_PARAM_LINKED"}), 5), decider, Config(), seed=5)
        return r
    a, b = run(), run()
    assert all(c["accepted"] for c in calls(a))
    assert json.dumps(a.trace, sort_keys=True) == json.dumps(b.trace, sort_keys=True)
    assert a.trace[0]["decider"] == decider and a.trace[0]["planted"] == ["F2_PARAM_LINKED"]


def test_code_deciders_give_their_rule_as_the_reason():
    """D32: policy sessions pass a fixed reason naming the decider's rule; it is in every ask_probe call."""
    for decider in ("fixed", "shuffled", "eig", "eig_explain"):
        r = run_policy_session(bank_student("s", frozenset({"F2_PARAM_LINKED"}), 2), decider, Config(), seed=2,
                               interpreter=OracleInterpreter(EXPL, 0.85, 0.05, random.Random(2)))
        probes = [c for c in calls(r) if c["tool"] == "ask_probe"]
        assert probes and all(c["accepted"] for c in probes), decider
        reasons = {c["args"]["reason"] for c in probes}
        assert len(reasons) == 1 and len(reasons.pop()) <= 200, decider
