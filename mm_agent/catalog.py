"""The misconception catalog: the fixed set of mental-model errors the agent can diagnose.

A student's mental model is represented as the subset of these misconceptions the student holds.
An empty subset is a viable model of the Python function-call notional machine (for this scope).

Two tiers:
- Assignment tier (prerequisites): what a variable is and what `=` does.
- Function tier: what a call, a parameter, a local variable and `return` do (the call stack).

The order of CATALOG is significant: when a student holds several misconceptions that each predict
a different answer to one probe, the earliest in this order decides the predicted answer
(see probes.Probe.intended). Assignment-tier entries come first because they are prerequisites.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Misconception:
    id: str
    tier: str  # "assignment" or "function"
    summary: str  # what the student believes, in one sentence
    signal: str  # what it typically looks like in an explanation


CATALOG: tuple[Misconception, ...] = (
    Misconception(
        "A1_LINKED", "assignment",
        "After `b = a`, the two variables stay linked, so a later assignment to one changes the other.",
        "Says b 'follows' or 'is tied to' a; expects b to change when a is reassigned.",
    ),
    Misconception(
        "A2_REVERSED", "assignment",
        "`x = y` copies the value from left to right (x's value goes into y).",
        "Reads assignment left-to-right; says the left variable 'gives' its value to the right one.",
    ),
    Misconception(
        "A3_COPY_ON_ASSIGN", "assignment",
        "`b = a` (or passing a list to a function) makes an independent copy of a list.",
        "Says b or the parameter is 'its own copy'; expects changes through one name not to show in the other.",
    ),
    Misconception(
        "F1_RETURN_IS_PRINT", "function",
        "`return` and `print` are the same: returning displays the value, and printing gives it back.",
        "Says a returned value 'shows up' on screen, or that a function that prints 'returns' that value.",
    ),
    Misconception(
        "F2_PARAM_LINKED", "function",
        "Reassigning a parameter inside a function changes the caller's variable.",
        "Says changing n inside the function 'changes x too' because x was passed in.",
    ),
    Misconception(
        "F3_DEF_RUNS_BODY", "function",
        "A function's body runs when the `def` is reached, not only when the function is called.",
        "Expects output from a function that was defined but never (or not yet) called.",
    ),
    Misconception(
        "F4_LOCALS_OUTLIVE_CALL", "function",
        "Variables created inside a function still exist after the call ends.",
        "Expects to use a function's local variable after the call; no idea of the frame going away.",
    ),
    Misconception(
        "F5_RUNS_AFTER_RETURN", "function",
        "Execution continues past `return`; the function keeps running the lines below it.",
        "Expects lines after return to run, or a later return to override an earlier one.",
    ),
)

IDS: tuple[str, ...] = tuple(m.id for m in CATALOG)
BY_ID: dict[str, Misconception] = {m.id: m for m in CATALOG}
