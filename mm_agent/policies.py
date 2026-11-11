"""Code deciders: fixed, shuffled, eig, eig_explain (specs/agent.md §2).

Each decider acts only through `Controller.handle(...)` with `actor="policy"`, so its sessions are
validated and traced exactly like the LLM interviewer's (architecture §1.4). A decider may read
`session.belief` to choose a probe (as the information-gain rule does) but never changes state.

Loop: choose a probe -> ask_probe -> (eig_explain only) ask_explanation after an answer that is not
correct, while explanations remain -> submit_diagnosis once the belief is confident, the probe budget
is spent, or no probe is left.

With `BankStudent(confidence_mode="none", vague_answer_rate=0)`, `Config(use_confidence=False)` and the
week-1 seeding, `eig` reproduces `poc.diagnose` (a regression test checks this).
"""

from __future__ import annotations

import random

from mm_agent.config import Config
from mm_agent.controller import Controller, SessionResult
from mm_agent.probes import BANK
from mm_agent.select import rank_probes
from mm_agent.session import Session
from mm_agent.tracing import run_extra, traceable

DECIDERS = ("fixed", "shuffled", "eig", "eig_explain")


def _next_probe(decider: str, session: Session, order: list[str]) -> str:
    unasked = session.unasked()
    if decider == "fixed":
        return unasked[0].id
    if decider == "shuffled":
        return next(pid for pid in order if pid not in session.asked)
    return rank_probes(session.belief, unasked)[0][0].id  # eig, eig_explain (D11 tie-break)


def run_policy_session(student, decider: str, config: Config, interpreter=None, session_id: str = "",
                       seed: int | None = None, shuffle_rng=None,
                       models: dict[str, str | None] | None = None) -> SessionResult:
    """Run one session with a code decider and return its result (trace included)."""
    if decider not in DECIDERS:
        raise ValueError(f"unknown decider {decider!r}; expected one of {DECIDERS}")
    if decider == "eig_explain" and interpreter is None:
        raise ValueError("eig_explain needs an interpreter")
    metadata = {"session_id": session_id, "decider": decider, "student_id": student.id}
    return _run_policy_session(student, decider, config, interpreter, session_id, seed, shuffle_rng, models,
                               **run_extra(metadata))


# D32: ask_probe requires a reason; the code deciders give a fixed one that names their rule.
POLICY_REASONS = {
    "fixed": "next probe in the fixed bank order",
    "shuffled": "next probe in this session's shuffled order",
    "eig": "top-ranked probe by expected information gain",
    "eig_explain": "top-ranked probe by expected information gain",
}


@traceable(run_type="chain", name="run_policy_session")
def _run_policy_session(student, decider, config, interpreter, session_id, seed, shuffle_rng, models):
    session = Session.new(student, interpreter, config, session_id=session_id, decider=decider,
                          models=models, seed=seed)
    controller = Controller(session, "policy")
    order = [p.id for p in BANK]
    if decider == "shuffled":
        rng = shuffle_rng or random.Random(f"{seed}-{student.id}-shuffle")
        rng.shuffle(order)
    while True:
        probe_id = _next_probe(decider, session, order)
        obs = controller.handle("ask_probe", {"probe_id": probe_id, "reason": POLICY_REASONS[decider]})
        if (decider == "eig_explain" and obs.accepted and obs.data["answer_matches"] != ["correct"]
                and len(session.explained) < config.max_explanations):
            controller.handle("ask_explanation", {})
        done = (session.belief.is_confident(config.low, config.high)
                or len(session.asked) >= config.max_probes or not session.unasked())
        if done or controller.check_terminal() is not None:
            break
    if controller.check_terminal() is None:
        controller.handle("submit_diagnosis", {})
        controller.check_terminal()
    return controller.result()
