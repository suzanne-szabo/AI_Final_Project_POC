"""Simulated students: a planted profile (the ground truth) plus random slips.

A simulated student answers each probe with the answer its profile predicts; with probability
`slip` it instead gives a different answer chosen uniformly from the probe's other options
(OTHER stands for an unanticipated answer).

Limitation: these students follow the same answer keys and slip model the belief state assumes,
so accuracy against them is an upper bound. The evaluation also uses a slip rate different from
the model's, and week 2 adds LLM-played students with free-text explanations.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from mm_agent.catalog import IDS
from mm_agent.probes import OTHER, Probe


@dataclass
class SimStudent:
    id: str
    profile: frozenset[str]
    slip: float
    rng: random.Random

    def answer(self, probe: Probe) -> str:
        intended = probe.intended(self.profile)
        if self.rng.random() >= self.slip:
            return intended
        others = [o for o in probe.options() if o != intended]
        choice = self.rng.choice(others)
        return "something unexpected" if choice == OTHER else choice


def random_profile(rng: random.Random, rate: float) -> frozenset[str]:
    return frozenset(m for m in IDS if rng.random() < rate)
