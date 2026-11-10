"""The probe bank: short Python programs the student traces ("what does this print?").

Each probe has the correct output and, for each misconception it is sensitive to, the output that a
student holding that misconception would predict (hand-written answer keys; architecture D5).
A test runs every probe in real Python to check the `correct` field.

Answers are compared after `normalize`: printed lines joined by " | ", whitespace collapsed,
lower-cased, and any answer mentioning an error collapsed to "error".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from mm_agent.catalog import IDS

OTHER = "<other>"  # any answer that matches neither the correct output nor a key


def normalize(answer: str) -> str:
    text = answer.strip().lower()
    if "error" in text or "exception" in text or "crash" in text:
        return "error"
    lines = [re.sub(r"\s+", " ", line).strip() for line in re.split(r"\n|\|", text)]
    return " | ".join(line for line in lines if line)


_HEDGES = re.compile(r"\b(?:i'm not sure|im not sure|not sure|i think|i guess|maybe|probably)\b")


def strip_hedges(text: str) -> str:
    """Remove hedge phrases from a student's answer before classification (specs/tools.md §2.2, D24).

    Lower-cases, removes "i think", "i guess", "maybe", "probably", "not sure", "i'm not sure",
    "im not sure" and every "?", then trims commas and whitespace from both ends. Text that is empty
    afterwards stays empty (and classifies as OTHER). `normalize` and `classify` are unchanged.
    """
    text = _HEDGES.sub("", text.lower()).replace("?", "")
    return text.strip(", \t\r\n")


@dataclass(frozen=True)
class Probe:
    id: str
    code: str
    correct: str
    keys: dict[str, str] = field(default_factory=dict)  # misconception id -> predicted answer
    kind: str = "trace"

    def intended(self, profile: frozenset[str]) -> str:
        """The answer a student with this profile would give, without slips."""
        for misconception in IDS:  # catalog order decides between competing keys
            if misconception in profile and misconception in self.keys:
                return self.keys[misconception]
        return self.correct

    def options(self) -> tuple[str, ...]:
        """Distinct answers the belief model distinguishes, in a stable order, ending with OTHER."""
        seen: list[str] = []
        for answer in (self.correct, *self.keys.values()):
            if answer not in seen:
                seen.append(answer)
        return (*seen, OTHER)

    def classify(self, answer: str) -> str:
        """Map a raw student answer onto one of `options()`."""
        normalized = normalize(answer)
        return normalized if normalized in self.options() else OTHER


BANK: tuple[Probe, ...] = (
    Probe("P01", "a = 5\nb = 3\nb = a\na = 7\nprint(a, b)", "7 5",
          {"A1_LINKED": "7 7", "A2_REVERSED": "7 3"}),
    Probe("P02", "x = 10\ny = 20\nx = y\nprint(x, y)", "20 20",
          {"A2_REVERSED": "10 10"}),
    Probe("P03", "a = [1, 2]\nb = a\nb.append(3)\nprint(a)", "[1, 2, 3]",
          {"A3_COPY_ON_ASSIGN": "[1, 2]", "A2_REVERSED": "error"}),
    Probe("P04", "nums = [4]\nother = nums\nother = [9]\nprint(nums)", "[4]",
          {"A1_LINKED": "[9]"}),
    Probe("P05", "def f():\n    print(3)\n\ny = f()\nprint(y)", "3 | none",
          {"F1_RETURN_IS_PRINT": "3 | 3"}),
    Probe("P06", "def double(n):\n    return n * 2\n\ndouble(4)\nprint(\"done\")", "done",
          {"F1_RETURN_IS_PRINT": "8 | done"}),
    Probe("P07", "def bump(n):\n    n = n + 1\n\nx = 5\nbump(x)\nprint(x)", "5",
          {"F2_PARAM_LINKED": "6"}),
    Probe("P08", "def greet():\n    print(\"hi\")\n\nprint(\"start\")", "start",
          {"F3_DEF_RUNS_BODY": "hi | start"}),
    Probe("P09", "def show():\n    print(\"A\")\n\nprint(\"B\")\nshow()", "b | a",
          {"F3_DEF_RUNS_BODY": "a | b | a"}),
    Probe("P10", "def make():\n    secret = 42\n\nmake()\nprint(secret)", "error",
          {"F4_LOCALS_OUTLIVE_CALL": "42"}),
    Probe("P11", "def setup():\n    value = 3\n    return value + 1\n\nresult = setup()\nprint(result, value)",
          "error", {"F4_LOCALS_OUTLIVE_CALL": "4 3"}),
    Probe("P12", "def check(n):\n    return n\n    print(\"after\")\n\nprint(check(2))", "2",
          {"F5_RUNS_AFTER_RETURN": "after | 2"}),
    Probe("P13", "def sign(x):\n    if x > 0:\n        return \"pos\"\n    return \"non-pos\"\n\nprint(sign(5))", "pos",
          {"F5_RUNS_AFTER_RETURN": "non-pos"}),
    Probe("P14", "def add(items):\n    items.append(1)\n\ndata = []\nadd(data)\nprint(data)", "[1]",
          {"A3_COPY_ON_ASSIGN": "[]"}),
    Probe("P15", "def triple(n):\n    n = n * 3\n    return n\n\nx = 2\ny = triple(x)\nprint(x, y)", "2 6",
          {"F2_PARAM_LINKED": "6 6"}),
)

BY_ID: dict[str, Probe] = {p.id: p for p in BANK}
