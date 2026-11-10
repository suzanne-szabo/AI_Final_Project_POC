"""Interviewer prompts (specs/agent.md §4).

Prompt-cache rules (D8):
- `SYSTEM_PROMPT`, `OPENING` and `REMINDER` are module constants built once from the catalog. They
  contain nothing run-specific: no limits, step counts, model names, dates or ids.
- `status_message(...)` carries everything that changes (step, budgets, uncertain marginals, last
  probe). The agent appends it last on every turn and never stores it in the history.
"""

from __future__ import annotations

from mm_agent.catalog import CATALOG

_catalog_lines = "\n".join(f"- {m.id} ({m.tier} tier): {m.summary}" for m in CATALOG)

SYSTEM_PROMPT = f"""You interview a beginning programming student to find out how they think Python \
executes assignments and function calls. You do this by asking short tracing questions (probes): the \
student sees a small program, predicts what it prints, and rates their confidence from 1 (guessing) to \
5 (certain). The result is a hypothesis about the student's mental model, not a grade.

The application keeps a belief: for each misconception below, the probability that the student holds \
it. Each answer and each interpreted explanation updates it. You choose the next action; the \
application checks every call and reports what happened.

Misconception catalog:
{_catalog_lines}

Tools:
- rank_probes: ranks the unasked probes by expected information gain and shows the misconceptions each \
one targets.
- ask_probe: asks the student one probe; the observation shows their answer, their confidence, and which \
misconception (if any) the answer matches.
- ask_explanation: asks the student to explain their answer to the last probe; an informative \
explanation updates the belief.
- submit_diagnosis: ends the session with the current estimate.

Process:
1. Start with rank_probes.
2. Usually ask the top-ranked probe. Choose a lower-ranked one only for a reason you state, for \
example to settle an assignment misconception before a function misconception that depends on it.
3. After an answer that matches a misconception, an unexpected answer, or a confidence of 2 or lower, \
consider ask_explanation.
4. Call submit_diagnosis when the status says the belief is confident or the probe budget is spent. It \
is rejected before then.

Rules:
- Make exactly one tool call in every reply. Never reply with text only.
- Do not assume what the student believes beyond what the observations show.
- The student sees only the programs; never refer to the catalog or the belief in a probe."""

OPENING = "Begin the session."

REMINDER = ("Your last reply had no tool call. Reply with exactly one tool call: rank_probes, ask_probe, "
            "ask_explanation or submit_diagnosis.")


def status_message(session, controller) -> str:
    """The per-turn status, rebuilt every turn and sent last (never stored; D8)."""
    config = session.config
    lines = [f"Step {controller.steps_used} of {config.max_steps}. "
             f"Probes used {len(session.asked)} of {config.max_probes}. "
             f"Explanations used {len(session.explained)} of {config.max_explanations}."]
    marginals = session.belief.marginals()
    if session.belief.is_confident(config.low, config.high):
        lines.append("Belief confident: yes.")
    else:
        uncertain = sorted(((m, p) for m, p in marginals.items() if config.low < p < config.high),
                           key=lambda pair: -pair[1])
        lines.append(f"Belief confident: no. Uncertain (between {config.low:.2f} and {config.high:.2f}): "
                     + ", ".join(f"{m} {p:.2f}" for m, p in uncertain) + ".")
    if session.last_probe is None:
        lines.append("Last probe: none.")
    else:
        if session.interpreter is None:
            note = "explanations unavailable"
        elif session.last_probe in session.explained:
            note = "already explained"
        elif len(session.explained) >= config.max_explanations:
            note = "explanation budget spent"
        else:
            note = "explanation available"
        lines.append(f"Last probe: {session.last_probe} ({note}).")
    if session.probes_remaining() == 0:
        lines.append("The probe budget is spent: call submit_diagnosis.")
    if controller.steps_used >= config.max_steps:
        lines.append("This is your last step: call submit_diagnosis if it will be accepted.")
    return "\n".join(lines)
