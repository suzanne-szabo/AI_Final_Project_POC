"""Offline tests for the catalog, probes, belief, selection and the code-only session."""

import contextlib
import io
import random

import pytest

from mm_agent.belief import PROFILES, Belief
from mm_agent.catalog import IDS
from mm_agent.poc import SessionConfig, diagnose
from mm_agent.probes import BANK, OTHER, normalize
from mm_agent.select import expected_information_gain, rank_probes
from mm_agent.students import SimStudent


def run_python(code: str) -> str:
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            exec(code, {})
    except Exception:
        return "error"
    return normalize(buffer.getvalue())


@pytest.mark.parametrize("probe", BANK, ids=lambda p: p.id)
def test_correct_answer_matches_real_python(probe):
    assert run_python(probe.code) == probe.correct


@pytest.mark.parametrize("probe", BANK, ids=lambda p: p.id)
def test_every_key_differs_from_correct_and_names_a_catalog_entry(probe):
    for misconception, answer in probe.keys.items():
        assert misconception in IDS
        assert answer != probe.correct


def test_every_misconception_is_targeted_by_at_least_two_probes():
    for m in IDS:
        assert sum(m in p.keys for p in BANK) >= 2, m


def test_normalize():
    assert normalize("3\nNone\n") == "3 | none"
    assert normalize("  7   5 ") == "7 5"
    assert normalize("NameError: name 'secret' is not defined") == "error"


def test_unanticipated_answer_classifies_as_other():
    assert BANK[0].classify("banana") == OTHER


def test_profiles_enumerate_all_subsets():
    assert len(PROFILES) == 2 ** len(IDS)
    assert len(set(PROFILES)) == len(PROFILES)


def test_belief_stays_normalized_and_moves_toward_evidence():
    belief = Belief(prior=0.2, slip=0.1)
    probe = next(p for p in BANK if p.id == "P05")
    before = belief.marginals()["F1_RETURN_IS_PRINT"]
    belief.update(probe, probe.keys["F1_RETURN_IS_PRINT"])
    assert sum(belief.weights) == pytest.approx(1.0)
    assert belief.marginals()["F1_RETURN_IS_PRINT"] > before
    assert sum(belief.predictive(probe).values()) == pytest.approx(1.0)


def test_information_gain_is_nonnegative_and_ranked():
    belief = Belief()
    ranked = rank_probes(belief, BANK)
    gains = [g for _, g in ranked]
    assert all(g >= -1e-12 for g in gains)
    assert gains == sorted(gains, reverse=True)
    assert expected_information_gain(belief, BANK[0]) > 0


@pytest.mark.parametrize("planted", [frozenset(), frozenset({"F1_RETURN_IS_PRINT"}),
                                     frozenset({"A1_LINKED", "F4_LOCALS_OUTLIVE_CALL"})])
def test_noise_free_student_is_diagnosed_exactly(planted):
    student = SimStudent("t", planted, slip=0.0, rng=random.Random(0))
    result = diagnose(student, "eig", SessionConfig(max_probes=15))
    assert result.diagnosis == planted
    kinds = [r["kind"] for r in result.records]
    assert kinds[0] == "header" and kinds[-1] == "result"


def test_budget_is_respected():
    student = SimStudent("t", frozenset(IDS), slip=0.5, rng=random.Random(3))
    result = diagnose(student, "eig", SessionConfig(max_probes=4))
    assert result.probes_used <= 4
    assert sum(r["kind"] == "probe" for r in result.records) == result.probes_used
