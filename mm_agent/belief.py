"""The belief state: an exact Bayesian posterior over every possible student profile.

With 8 misconceptions there are 2**8 = 256 profiles, few enough to enumerate, so no independence
assumption is needed after the prior.

All sums use math.fsum, which is correctly rounded on every Python version. Plain sum() changed
in Python 3.12, which made runs with the same seed differ between Python versions (D11). The likelihood is a slip model: a student gives the answer
their profile predicts with probability 1 - slip, and otherwise any other option uniformly.

The belief state is application-owned. The LLM may read a summary of it but never writes it.

Week 2 (specs/belief.md) adds confidence-rated answers (D19), explanation evidence (D13, D21),
`is_confident` and `estimate`. Calls without a confidence rating behave exactly as in week 1.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable

from mm_agent.catalog import IDS
from mm_agent.probes import Probe

PROFILES: tuple[frozenset[str], ...] = tuple(
    frozenset(combo) for size in range(len(IDS) + 1) for combo in itertools.combinations(IDS, size)
)


def entropy(weights: list[float]) -> float:
    return -math.fsum(w * math.log2(w) for w in weights if w > 0)


class Belief:
    def __init__(self, prior: float = 0.2, slip: float = 0.1):
        self.prior = prior
        self.slip = slip
        self.weights = [prior ** len(p) * (1 - prior) ** (len(IDS) - len(p)) for p in PROFILES]
        self._normalize()

    def _normalize(self) -> None:
        total = math.fsum(self.weights)
        self.weights = [w / total for w in self.weights]

    def likelihood(self, probe: Probe, option: str, profile: frozenset[str], slip: float | None = None) -> float:
        slip = self.slip if slip is None else slip
        if option == probe.intended(profile):
            return 1 - slip
        return slip / (len(probe.options()) - 1)

    def update(self, probe: Probe, option: str, confidence: int | None = None,
               slip_by_confidence: dict[int, float] | None = None) -> None:
        """Condition on the student giving `option` (already classified by Probe.classify).

        With a confidence rating and a slip table, the slip for that rating is used (specs/belief.md §2,
        D19); otherwise `self.slip`, exactly as in week 1.
        """
        slip = None
        if confidence is not None and slip_by_confidence is not None:
            if confidence not in (1, 2, 3, 4, 5):
                raise ValueError(f"confidence must be 1-5, got {confidence!r}")
            slip = slip_by_confidence[confidence]
        self.weights = [w * self.likelihood(probe, option, p, slip) for w, p in zip(self.weights, PROFILES)]
        self._normalize()

    def update_explanation(self, probe: Probe, labels: Iterable[str], sensitivity: float,
                           false_alarm: float, scope: Iterable[str] | None = None) -> None:
        """Condition on an interpreter's labels for an explanation of `probe` (specs/belief.md §3).

        Only the scored set is scored: the probe's relevant misconceptions (`probe.keys`, D21), narrowed
        to `scope` when given (D27). Other labels are ignored here and recorded by the caller. An empty
        label list is evidence against each scored misconception.
        """
        labels = set(labels)
        unknown = sorted(labels - set(IDS))
        if unknown:
            raise ValueError(f"unknown misconception ids: {unknown}")
        if not 0 < false_alarm < sensitivity < 1:
            raise ValueError(f"need 0 < false_alarm < sensitivity < 1, got {false_alarm}, {sensitivity}")
        relevant = [m for m in IDS if m in probe.keys]
        if scope is not None:
            scope = set(scope)
            if scope - set(IDS):
                raise ValueError(f"unknown misconception ids in scope: {sorted(scope - set(IDS))}")
            relevant = [m for m in relevant if m in scope]
            if not relevant:
                raise ValueError(f"scope {sorted(scope)} has no id relevant to {probe.id}")

        def factor(profile: frozenset[str]) -> float:
            result = 1.0
            for m in relevant:
                if m in labels:
                    result *= sensitivity if m in profile else false_alarm
                else:
                    result *= (1 - sensitivity) if m in profile else (1 - false_alarm)
            return result

        self.weights = [w * factor(p) for w, p in zip(self.weights, PROFILES)]
        self._normalize()

    def is_confident(self, low: float, high: float) -> bool:
        """Every marginal is <= low or >= high."""
        return all(p <= low or p >= high for p in self.marginals().values())

    def estimate(self) -> dict:
        """The current estimate: rounded marginals, the ids above 0.5 (catalog order), the entropy."""
        marginals = self.marginals()
        return {"marginals": {m: round(p, 4) for m, p in marginals.items()},
                "most_likely": [m for m, p in marginals.items() if p > 0.5],
                "entropy": round(self.entropy(), 4)}

    def predictive(self, probe: Probe) -> dict[str, float]:
        """Probability of each option for this probe under the current belief."""
        return {
            option: math.fsum(w * self.likelihood(probe, option, p) for w, p in zip(self.weights, PROFILES))
            for option in probe.options()
        }

    def marginals(self) -> dict[str, float]:
        """P(student holds misconception m) for each m, in catalog order."""
        return {m: math.fsum(w for w, p in zip(self.weights, PROFILES) if m in p) for m in IDS}

    def entropy(self) -> float:
        return entropy(self.weights)

    def map_profile(self) -> frozenset[str]:
        return PROFILES[max(range(len(PROFILES)), key=self.weights.__getitem__)]

    def copy(self) -> "Belief":
        clone = Belief.__new__(Belief)
        clone.prior, clone.slip, clone.weights = self.prior, self.slip, list(self.weights)
        return clone
