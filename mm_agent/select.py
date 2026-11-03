"""Probe selection policies.

- `eig`: pick the unused probe with the highest expected information gain (expected reduction in
  the entropy of the belief over profiles). This is classical computerized adaptive testing.
- `fixed`: the bank in order; the non-adaptive baseline.

In week 2 the ReAct interviewer calls `rank_probes` (which uses `expected_information_gain`) and
chooses among the top candidates; these two policies remain as baselines.
"""

from __future__ import annotations

from collections.abc import Iterable

from mm_agent.belief import Belief
from mm_agent.probes import Probe


def expected_information_gain(belief: Belief, probe: Probe) -> float:
    before = belief.entropy()
    expected_after = 0.0
    for option, p_option in belief.predictive(probe).items():
        if p_option <= 0:
            continue
        after = belief.copy()
        after.update(probe, option)
        expected_after += p_option * after.entropy()
    return before - expected_after


def rank_probes(belief: Belief, candidates: Iterable[Probe]) -> list[tuple[Probe, float]]:
    """Candidates by expected information gain, best first; ties keep bank order."""
    scored = [(probe, expected_information_gain(belief, probe)) for probe in candidates]
    return sorted(scored, key=lambda pair: -pair[1])


def choose(policy: str, belief: Belief, unused: list[Probe]) -> Probe:
    if policy == "fixed":
        return unused[0]
    if policy == "eig":
        return rank_probes(belief, unused)[0][0]
    raise ValueError(f"unknown policy {policy!r}")
