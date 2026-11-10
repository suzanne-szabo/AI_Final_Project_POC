"""The controller: the single gatekeeper between deciders and session state (specs/controller.md).

Every tool call, from a code policy or the LLM interviewer, goes through `handle` (or `validate` then
`execute`). Policies P1-P8 are checked in order; a rejected call changes nothing except the counters
and the trace (architecture §1.2). The controller is the only code that sets the terminal reason
(§4), and it owns the append-only trace (§6).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from mm_agent import tools
from mm_agent.prompts import REMINDER
from mm_agent.students import SimStudent
from mm_agent.tracing import header_info


@dataclass(frozen=True)
class Approval:
    tool: str
    args: BaseModel
    raw_args: dict


@dataclass(frozen=True)
class Observation:
    tool: str
    accepted: bool
    message: str
    data: dict
    policy: str | None = None

    def as_dict(self) -> dict:
        out = {"tool": self.tool, "accepted": self.accepted, "message": self.message, "data": self.data}
        if not self.accepted and self.policy is not None:
            out["policy"] = self.policy
        return out

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True)


@dataclass(frozen=True)
class Terminal:
    reason: str  # DIAGNOSED, BUDGET, ERROR, STEP_LIMIT
    error_kind: str | None = None  # MODEL_ERROR, NO_ACTION, REJECTION_LIMIT


@dataclass(frozen=True)
class SessionResult:
    terminal: str
    error_kind: str | None
    estimate: dict | None
    planted: list[str]
    exact_match: bool | None
    probes_used: int
    explanations_used: int
    steps_used: int
    rejections_total: int
    model_calls: int
    model_seconds: float
    trace: list[dict] = field(repr=False)


ACCEPT_MESSAGES = {
    "rank_probes": "Probes ranked by expected information gain.",
    "ask_probe": "Answer recorded.",
    "ask_explanation": "Explanation recorded.",
    "submit_diagnosis": "Diagnosis submitted. The session is over.",
}


def student_kind(student) -> str:
    """`bank`, `llm`, `sim` or `scripted`, for the trace header."""
    if isinstance(student, SimStudent):
        return "sim"
    return getattr(student, "kind", type(student).__name__)


class Controller:
    def __init__(self, session, actor: str):
        if actor not in ("model", "policy"):
            raise ValueError(f"actor must be 'model' or 'policy', got {actor!r}")
        self.session = session
        self.actor = actor
        self.trace: list[dict] = []
        self.steps_used = 0
        self.consecutive_rejections = 0
        self.rejections_total = 0
        self.model_calls = 0
        self.model_seconds = 0.0
        self.terminal: Terminal | None = None
        self._calls = 0  # tool calls handled, used as the step number for the policy actor
        self._model_error = False
        self._no_action_terminal = False
        self._last_reply_no_action = False
        self._step_model: dict | None = None  # latency and usage of this step's model call
        self._result: SessionResult | None = None
        student = session.student
        profile = getattr(student, "profile", None)
        self.planted = sorted(profile) if profile is not None else []
        self._append({"kind": "header", "session_id": session.session_id, "student_id": student.id,
                      "student_kind": student_kind(student), "planted": self.planted,
                      "decider": session.decider, "models": dict(session.models),
                      "config": session.config.as_dict(), "seed": session.seed, "tracing": header_info()})

    # --- trace -----------------------------------------------------------------------------------------

    def _append(self, record: dict) -> None:
        record["seq"] = len(self.trace) + 1
        self.trace.append(record)

    def _step(self) -> int:
        return self.steps_used if self.actor == "model" else self._calls

    def _model_event(self, event: str, text: str) -> None:
        self._append({"kind": "model", "step": self._step(), "event": event, "text": text})

    def _record_call(self, tool: str, raw_args, obs: Observation) -> None:
        record = {"kind": "call", "step": self._step(), "actor": self.actor, "tool": tool, "args": raw_args,
                  "accepted": obs.accepted, "message": obs.message, "data": obs.data,
                  "probes_used": len(self.session.asked), "explanations_used": len(self.session.explained),
                  "steps_used": self.steps_used}
        if not obs.accepted:
            record["policy"] = obs.policy
        if self._step_model is not None:  # the step's model latency and usage go on its first call
            record["model"] = self._step_model
            self._step_model = None
        self._append(record)

    # --- steps and model events --------------------------------------------------------------------------

    def begin_step(self) -> None:
        """One model call = one step (model actor only)."""
        if self.actor != "model":
            raise RuntimeError("begin_step is for the model actor only")
        self.steps_used += 1
        self._step_model = None

    def record_model_call(self, seconds: float, usage: dict | None = None) -> None:
        """Add one interviewer call's latency (and usage) to the counters and the step's call record."""
        self.model_calls += 1
        self.model_seconds += seconds
        self._step_model = {"seconds": round(seconds, 3), "usage": dict(usage or {})}

    def record_thought(self, text: str) -> None:
        self._model_event("thought", text)

    def record_no_action(self) -> Observation | None:
        """A reply with no tool call: a reminder the first time (counts as a rejection), None the second."""
        self._model_event("no_action", "reply had no tool call")
        if self._last_reply_no_action:
            self._no_action_terminal = True
            return None
        self._last_reply_no_action = True
        self.consecutive_rejections += 1
        self.rejections_total += 1
        self._model_event("reminder", REMINDER)
        return Observation("none", False, REMINDER, {})

    def record_model_error(self, error: BaseException) -> None:
        self._model_error = True
        self._model_event("model_error", f"{type(error).__name__}: {error}")

    # --- validation and execution --------------------------------------------------------------------

    def _reject(self, tool: str, raw_args, policy: str, message: str) -> Observation:
        obs = Observation(tool, False, message, {}, policy)
        self.consecutive_rejections += 1
        self.rejections_total += 1
        self._record_call(tool, raw_args, obs)
        return obs

    def _remaining_note(self) -> str:
        return f"{self.session.probes_remaining()} probes remain"

    def validate(self, tool: str, raw_args) -> Approval | Observation:
        """Check P1-P7 in order. Returns an Approval, or the rejection Observation (already traced)."""
        self._calls += 1
        self._last_reply_no_action = False
        session, config = self.session, self.session.config
        if self.terminal is not None or session.outcome is not None:
            return self._reject(tool, raw_args, "P1", "The session has ended; no further calls are accepted.")
        if tool not in tools.SCHEMAS:
            return self._reject(tool, raw_args, "P2", f"Unknown tool {tool!r}. The tools are "
                                f"{', '.join(tools.TOOL_NAMES)}.")
        if not isinstance(raw_args, dict):
            return self._reject(tool, raw_args, "P3", f"Arguments for {tool} must be a JSON object.")
        try:
            args = tools.SCHEMAS[tool].model_validate(raw_args)
        except ValidationError as error:
            problems = "; ".join(f"{'.'.join(str(x) for x in e['loc']) or 'arguments'}: {e['msg']}"
                                 for e in error.errors())
            return self._reject(tool, raw_args, "P3", f"Invalid arguments for {tool}: {problems}.")
        if tool == "ask_probe":
            if args.probe_id in session.asked:
                return self._reject(tool, raw_args, "P4", f"{args.probe_id} was already asked in this session. "
                                    f"Asked so far: {', '.join(session.asked)}. Choose an unasked probe "
                                    f"(rank_probes lists them).")
            if len(session.asked) >= config.max_probes:
                return self._reject(tool, raw_args, "P5", f"The probe budget is spent ({len(session.asked)} of "
                                    f"{config.max_probes} probes used): call submit_diagnosis.")
        if tool == "ask_explanation":
            reason = None
            if session.last_probe is None:
                reason = "no probe has been asked yet; ask a probe first"
            elif session.last_probe in session.explained:
                reason = f"the last probe ({session.last_probe}) was already explained; ask another probe first"
            elif len(session.explained) >= config.max_explanations:
                reason = (f"the explanation budget is spent ({len(session.explained)} of "
                          f"{config.max_explanations} used)")
            elif session.interpreter is None:
                reason = "explanations are not available in this session"
            if reason:
                return self._reject(tool, raw_args, "P6", f"Cannot ask for an explanation: {reason}.")
        if tool == "submit_diagnosis" and not session.belief.is_confident(config.low, config.high):
            remaining = session.probes_remaining()
            if remaining > 0:
                uncertain = sum(config.low < p < config.high for p in session.belief.marginals().values())
                return self._reject(tool, raw_args, "P7", f"Not confident yet: {uncertain} misconceptions are "
                                    f"between {config.low} and {config.high}, and {remaining} probes remain. "
                                    f"Ask more probes first.")
        return Approval(tool, args, raw_args)

    def execute(self, approval: Approval) -> Observation:
        """Run an approved call through `tools`, record it, and reset the consecutive-rejection count."""
        data = tools.execute(self.session, approval.tool, approval.args)
        obs = Observation(approval.tool, True, ACCEPT_MESSAGES[approval.tool], data)
        self.consecutive_rejections = 0
        self._record_call(approval.tool, approval.raw_args, obs)
        if approval.tool in ("ask_probe", "ask_explanation"):
            belief = self.session.belief
            self._append({"kind": "belief", "step": self._step(), "after": approval.tool,
                          "entropy": round(belief.entropy(), 4), "marginals": tools.rounded(belief.marginals())})
        return obs

    def handle(self, tool: str, raw_args) -> Observation:
        checked = self.validate(tool, raw_args)
        return checked if isinstance(checked, Observation) else self.execute(checked)

    def reject_extra_call(self, tool: str, raw_args) -> Observation:
        """P8: every call after the first in one model reply. Does not count toward the rejection limit."""
        obs = Observation(tool, False, "Only the first tool call in a reply is used; this call was ignored. "
                          "Make exactly one tool call per reply.", {}, "P8")
        self._record_call(tool, raw_args, obs)
        return obs

    # --- terminal and result ---------------------------------------------------------------------------

    def check_terminal(self) -> Terminal | None:
        """Checked after every step; the first match wins and, once set, is final (§4)."""
        if self.terminal is not None:
            return self.terminal
        config = self.session.config
        if self.session.outcome is not None:
            self.terminal = Terminal(self.session.outcome)
        elif self._model_error:
            self.terminal = Terminal("ERROR", "MODEL_ERROR")
        elif self._no_action_terminal:
            self.terminal = Terminal("ERROR", "NO_ACTION")
        elif self.consecutive_rejections >= config.max_consecutive_rejections:
            self.terminal = Terminal("ERROR", "REJECTION_LIMIT")
        elif self.actor == "model" and self.steps_used >= config.max_steps:
            self.terminal = Terminal("STEP_LIMIT")
        return self.terminal

    def result(self) -> SessionResult:
        """Append the result record (once) and return the SessionResult. Needs a terminal reason."""
        if self._result is not None:
            return self._result
        if self.terminal is None:
            raise RuntimeError("result() needs a terminal reason; call check_terminal() first")
        session = self.session
        estimate = session.estimate
        exact = None if estimate is None else set(estimate["most_likely"]) == set(self.planted)
        record = {"kind": "result", "terminal": self.terminal.reason, "error_kind": self.terminal.error_kind,
                  "estimate": estimate, "planted": self.planted, "exact_match": exact,
                  "probes_used": len(session.asked), "explanations_used": len(session.explained),
                  "steps_used": self.steps_used, "rejections_total": self.rejections_total,
                  "model_calls": self.model_calls, "model_seconds": round(self.model_seconds, 3)}
        self._append(record)
        self._result = SessionResult(
            terminal=record["terminal"], error_kind=record["error_kind"], estimate=estimate,
            planted=list(self.planted), exact_match=exact, probes_used=record["probes_used"],
            explanations_used=record["explanations_used"], steps_used=self.steps_used,
            rejections_total=self.rejections_total, model_calls=self.model_calls,
            model_seconds=record["model_seconds"], trace=self.trace)
        return self._result
