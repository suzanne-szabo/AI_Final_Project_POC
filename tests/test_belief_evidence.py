"""Black-box tests for specs/belief.md (confidence and explanation evidence)."""

import pytest

from mm_agent.belief import Belief
from mm_agent.catalog import IDS
from mm_agent.config import Config
from mm_agent.probes import BY_ID

P07 = BY_ID["P07"]
F2 = "F2_PARAM_LINKED"
SLIPS = Config().slip_by_confidence


def test_update_without_confidence_matches_week1_behavior():
    a, b = Belief(0.2, 0.1), Belief(0.2, 0.1)
    for probe_id, option in [("P01", "7 7"), ("P07", "6"), ("P10", "error")]:
        a.update(BY_ID[probe_id], option)
        b.update(BY_ID[probe_id], option, confidence=None, slip_by_confidence=SLIPS)
    assert a.weights == b.weights


def test_confidence_sets_the_slip():
    high, low = Belief(0.2, 0.1), Belief(0.2, 0.1)
    high.update(P07, "6", confidence=5, slip_by_confidence=SLIPS)
    low.update(P07, "6", confidence=1, slip_by_confidence=SLIPS)
    assert high.marginals()[F2] == pytest.approx(0.92, abs=0.01)
    assert low.marginals()[F2] == pytest.approx(0.48, abs=0.01)


@pytest.mark.parametrize("bad", [0, 6, -1])
def test_confidence_out_of_range_is_rejected(bad):
    with pytest.raises(ValueError):
        Belief().update(P07, "6", confidence=bad, slip_by_confidence=SLIPS)


def test_default_config_values():
    c = Config()
    assert c.slip_by_confidence == {1: 0.35, 2: 0.20, 3: 0.10, 4: 0.06, 5: 0.04}
    assert (c.max_probes, c.max_explanations, c.max_steps, c.max_consecutive_rejections) == (10, 5, 30, 3)
    assert (c.low, c.high, c.prior, c.model_slip) == (0.15, 0.85, 0.2, 0.10)
    assert (c.interpreter_sensitivity, c.interpreter_false_alarm) == (0.85, 0.05)
    assert c.use_confidence is True and c.rank_k == 3


def test_worked_example_from_spec():
    b = Belief(0.2, 0.1)
    b.update(P07, "6")
    assert b.marginals()[F2] == pytest.approx(0.82, abs=0.005)
    labeled, empty = b.copy(), b.copy()
    labeled.update_explanation(P07, [F2], 0.85, 0.05)
    empty.update_explanation(P07, [], 0.85, 0.05)
    assert labeled.marginals()[F2] == pytest.approx(0.99, abs=0.005)
    assert empty.marginals()[F2] == pytest.approx(0.42, abs=0.005)


def test_labels_outside_the_probe_are_ignored():
    a, b = Belief(), Belief()
    a.update_explanation(P07, ["A1_LINKED", "F5_RUNS_AFTER_RETURN"], 0.85, 0.05)
    b.update_explanation(P07, [], 0.85, 0.05)
    assert a.weights == pytest.approx(b.weights)
    assert a.marginals()["A1_LINKED"] == pytest.approx(0.2)


def test_explanation_update_stays_normalized():
    b = Belief()
    b.update_explanation(BY_ID["P01"], ["A1_LINKED"], 0.85, 0.05)
    assert sum(b.weights) == pytest.approx(1.0)


def test_unknown_label_is_rejected():
    with pytest.raises(ValueError):
        Belief().update_explanation(P07, ["NOT_AN_ID"], 0.85, 0.05)


@pytest.mark.parametrize("sens,fa", [(0.05, 0.85), (1.0, 0.05), (0.85, 0.0), (0.5, 0.5)])
def test_invalid_rates_are_rejected(sens, fa):
    with pytest.raises(ValueError):
        Belief().update_explanation(P07, [F2], sens, fa)


def test_is_confident_and_estimate():
    b = Belief(0.2, 0.1)
    assert not b.is_confident(0.15, 0.85)
    assert b.is_confident(0.25, 0.75)
    est = b.estimate()
    assert set(est) == {"marginals", "most_likely", "entropy"}
    assert list(est["marginals"]) == list(IDS)
    assert est["most_likely"] == []
    b.update(P07, "6", confidence=5, slip_by_confidence=SLIPS)
    assert b.estimate()["most_likely"] == [F2]
    assert all(round(v, 4) == v for v in b.estimate()["marginals"].values())
