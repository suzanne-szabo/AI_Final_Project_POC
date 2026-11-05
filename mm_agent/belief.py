"""The belief state: an exact Bayesian posterior over every possible student profile.

With 8 misconceptions there are 2**8 = 256 profiles, few enough to enumerate, so no independence
assumption is needed after the prior.

All sums use math.fsum, which is correctly rounded on every Python version. Plain sum() changed
in Python 3.12, which made runs with the same seed differ between Python versions (D11). The likelihood is a slip model: a student gives the answer
their profile predicts with probability 1 - slip, and otherwise any other option uniformly.

The belief state is application-owned. The LLM may read a summary of it but never writes it.
"""

from __future__ import annotations

import itertools
import math

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

    def likelihood(self, probe: Probe, option: str, profile: frozenset[str]) -> float:
        if option == probe.intended(profile):
            return 1 - self.slip
        return self.slip / (len(probe.options()) - 1)

    def update(self, probe: Probe, option: str) -> None:
        """Condition on the student giving `option` (already classified by Probe.classify)."""
        self.weights = [w * self.likelihood(probe, option, p) for w, p in zip(self.weights, PROFILES)]
        self._normalize()

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
