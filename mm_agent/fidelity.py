"""Fidelity check for LLM students (specs/students.md §6, docs/student-simulator-plan.md §3.1, D35).

Before LLM students are used to grade the agent, check that each one answers the way its planted profile
predicts. Every student gets every probe, with no interviewer and no belief state, and each answer is
compared with `probe.intended(profile)`.

Outcomes for one answer (after `strip_hedges` and `probe.classify`):

- On a **belief probe** (the profile predicts a wrong answer, `intended != correct`):
  - `faithful`: the answer is the predicted wrong answer;
  - `leak`: the answer is correct (the model "knows Python" and drops the persona; the main risk);
  - `other_key`: the answer is a different misconception's key;
  - `unexpected`: the answer matches nothing.
- On a **neutral probe** (`intended == correct`):
  - `faithful`: correct;
  - `invented`: the answer is a misconception's key the student does not hold;
  - `unexpected`: the answer matches nothing.

Measures (direction in brackets):
- belief fidelity = faithful / belief answers [higher is better];
- leak rate = leak / belief answers [lower is better];
- neutral accuracy = faithful / neutral answers [higher is better];
- invented rate = invented / neutral answers [lower is better].
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from mm_agent.catalog import IDS
from mm_agent.probes import BANK, OTHER, Probe, strip_hedges

# Ordered so that a small first run (--n 4) already covers no misconception, an assignment one, and two
# function ones; then the other singles; then three pairs that share probes or interact.
DEFAULT_PROFILES: tuple[frozenset[str], ...] = (
    frozenset(),
    frozenset({"A3_COPY_ON_ASSIGN"}),
    frozenset({"F2_PARAM_LINKED"}),
    frozenset({"F1_RETURN_IS_PRINT"}),
    frozenset({"A1_LINKED"}),
    frozenset({"F5_RUNS_AFTER_RETURN"}),
    frozenset({"F3_DEF_RUNS_BODY"}),
    frozenset({"F4_LOCALS_OUTLIVE_CALL"}),
    frozenset({"A2_REVERSED"}),
    frozenset({"A1_LINKED", "F2_PARAM_LINKED"}),
    frozenset({"A3_COPY_ON_ASSIGN", "F1_RETURN_IS_PRINT"}),
    frozenset({"F3_DEF_RUNS_BODY", "F5_RUNS_AFTER_RETURN"}),
)


def deciding_misconception(probe: Probe, profile: frozenset[str]) -> str | None:
    """The held misconception whose key decides the intended answer (catalog order), or None."""
    for m in IDS:
        if m in profile and m in probe.keys:
            return m
    return None


@dataclass(frozen=True)
class Scored:
    student: str
    profile: tuple[str, ...]
    style: str | None
    probe_id: str
    answer: str
    confidence: int | None
    classified: str
    intended: str
    belief_probe: bool
    misconception: str | None  # the one deciding `intended` on a belief probe
    outcome: str


def score_answer(student: str, profile: frozenset[str], style: str | None, probe: Probe,
                 answer: str, confidence: int | None) -> Scored:
    classified = probe.classify(strip_hedges(answer))
    intended = probe.intended(profile)
    belief = intended != probe.correct
    if classified == intended:
        outcome = "faithful"
    elif classified == OTHER:
        outcome = "unexpected"
    elif belief:
        outcome = "leak" if classified == probe.correct else "other_key"
    else:
        outcome = "invented"
    return Scored(student, tuple(sorted(profile)), style, probe.id, answer, confidence, classified, intended,
                  belief, deciding_misconception(probe, profile) if belief else None, outcome)


def _rate(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


def summarize(records: list[Scored]) -> dict:
    belief = [r for r in records if r.belief_probe]
    neutral = [r for r in records if not r.belief_probe]
    b, n = Counter(r.outcome for r in belief), Counter(r.outcome for r in neutral)
    per_m: dict[str, Counter] = defaultdict(Counter)
    for r in belief:
        per_m[r.misconception][r.outcome] += 1

    def conf(rows):
        values = [r.confidence for r in rows if r.confidence is not None]
        return round(statistics.mean(values), 2) if values else None

    return {
        "answers": len(records),
        "belief_answers": len(belief),
        "neutral_answers": len(neutral),
        "belief_fidelity": _rate(b["faithful"], len(belief)),
        "leak_rate": _rate(b["leak"], len(belief)),
        "belief_unexpected_rate": _rate(b["unexpected"], len(belief)),
        "other_key_rate": _rate(b["other_key"], len(belief)),
        "neutral_accuracy": _rate(n["faithful"], len(neutral)),
        "invented_rate": _rate(n["invented"], len(neutral)),
        "neutral_unexpected_rate": _rate(n["unexpected"], len(neutral)),
        "mean_confidence_faithful_belief": conf([r for r in belief if r.outcome == "faithful"]),
        "mean_confidence_leak": conf([r for r in belief if r.outcome == "leak"]),
        "mean_confidence_neutral": conf(neutral),
        "per_misconception": {
            m: {"answers": sum(c.values()), "fidelity": _rate(c["faithful"], sum(c.values())),
                "leak": _rate(c["leak"], sum(c.values())), "unexpected": _rate(c["unexpected"], sum(c.values()))}
            for m, c in sorted(per_m.items())
        },
    }


def run_student(student, probes: tuple[Probe, ...] = BANK, explain: bool = False) -> tuple[list[Scored], dict]:
    """Ask one student every probe; on belief probes optionally ask for an explanation.

    Returns the scored answers and a dict of explanations by probe id (for hand labeling, E5).
    """
    scored, explanations = [], {}
    for probe in probes:
        response = student.answer(probe)
        s = score_answer(student.id, student.profile, getattr(student, "style", None), probe,
                         response.answer, response.confidence)
        scored.append(s)
        if explain and s.belief_probe:
            explanations[probe.id] = student.explain(probe)
    return scored, explanations


def as_dict(record: Scored) -> dict:
    return asdict(record)
