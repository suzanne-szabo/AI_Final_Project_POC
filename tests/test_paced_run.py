"""Tests for scripts/paced_run.py: a session that hit the budget cap is rerun from a fresh copy."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

SPEC = importlib.util.spec_from_file_location("paced_run", Path(__file__).resolve().parent.parent / "scripts" / "paced_run.py")
paced_run = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(paced_run)


class Stu:
    def __init__(self):
        self.id, self.state, self.failures = "s1", 0, 0


def test_rerun_after_budget_error_uses_a_fresh_copy_and_waits():
    seen, waits, logs = [], [], []

    def session(student, x):
        student.state += 1                 # sessions change the student
        seen.append(student.state)
        text = "ExceededBudget: Key over 1h budget" if len(seen) == 1 else "ok"
        return SimpleNamespace(trace=[{"kind": "model", "text": text}])

    wrapped = paced_run.paced(session, 5, 3, logs.append, sleep=waits.append)
    stu = Stu()
    result = wrapped(stu, 1)
    assert result.trace[0]["text"] == "ok"
    assert seen == [1, 1]                  # the second attempt started from the original state
    assert waits == [5] and len(logs) == 1 and logs[0]["student"] == "s1"
    assert stu.state == 1                  # the caller's student reflects the kept attempt


def test_gives_up_after_max_waits():
    def session(student):
        return SimpleNamespace(trace=["ExceededBudget"])
    waits = []
    result = paced_run.paced(session, 1, 2, lambda e: None, sleep=waits.append)(Stu())
    assert waits == [1, 1] and paced_run.budget_hit(result)
