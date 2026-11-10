"""One diagnostic session's state (specs/controller.md §1).

The composition root for a session: the student, the interpreter, the configuration, the belief, the
probes and explanations asked, and the final estimate. Only `tools` changes it (architecture §5.4);
deciders may read `session.belief` but never write it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mm_agent.belief import Belief
from mm_agent.config import Config
from mm_agent.probes import BANK


@dataclass
class Session:
    student: object  # a Student (students.py); SimStudent is also accepted for the trace header
    interpreter: object | None  # an Interpreter (interpret.py), or None for deciders that never explain
    config: Config
    belief: Belief
    session_id: str = ""
    decider: str = ""
    models: dict[str, str | None] = field(default_factory=dict)
    seed: int | None = None
    asked: list[str] = field(default_factory=list)  # probe ids, in order
    answers: dict = field(default_factory=dict)  # probe id -> Response
    last_probe: str | None = None
    explained: set[str] = field(default_factory=set)
    estimate: dict | None = None
    outcome: str | None = None  # "DIAGNOSED" or "BUDGET" once submit_diagnosis is accepted

    @classmethod
    def new(cls, student, interpreter, config: Config, session_id: str, decider: str,
            models: dict[str, str | None] | None = None, seed: int | None = None) -> "Session":
        names = {"interviewer": None, "interpreter": None, "student": None}
        names.update(models or {})
        return cls(student=student, interpreter=interpreter, config=config,
                   belief=Belief(config.prior, config.model_slip), session_id=session_id,
                   decider=decider, models=names, seed=seed)

    def unasked(self) -> list:
        """Probes not yet asked, in bank order."""
        return [p for p in BANK if p.id not in self.asked]

    def probes_remaining(self) -> int:
        """Probes that may still be asked: the budget left, capped by the probes left in the bank."""
        return max(0, min(self.config.max_probes - len(self.asked), len(self.unasked())))
