"""The four interviewer tools: argument schemas, definitions and executors (specs/tools.md).

- `SCHEMAS` maps each tool name to its Pydantic argument schema (`extra="forbid"`, strict types), used
  by the controller's P3 check.
- `tool_definitions()` returns the OpenAI-format definitions, built once at import in the fixed order
  rank_probes, ask_probe, ask_explanation, submit_diagnosis (D8: identical bytes on every call).
- `execute(session, tool, args)` runs a call the controller has already approved and returns the
  observation's `data`. Executors are the only code that updates the belief or questions the student
  (architecture §6). Each is wrapped with `tracing.traceable(run_type="tool")`.
"""

from __future__ import annotations

import copy
import json

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mm_agent.catalog import IDS
from mm_agent.probes import BY_ID, strip_hedges
from mm_agent.select import rank_probes as rank_by_gain
from mm_agent.tracing import traceable

TOOL_NAMES = ("rank_probes", "ask_probe", "ask_explanation", "submit_diagnosis")


# --- argument schemas ----------------------------------------------------------------------------------

class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RankProbesArgs(_Args):
    # Omitted k means Config.rank_k (default 3); see docs/implementer-notes.md.
    k: int | None = Field(default=None, ge=1, le=8)


class AskProbeArgs(_Args):
    probe_id: str = Field(pattern=r"^P\d{2}$")

    @field_validator("probe_id")
    @classmethod
    def _known(cls, value: str) -> str:
        if value not in BY_ID:
            raise ValueError(f"unknown probe id {value!r}; probes are P01 to P{len(BY_ID):02d}")
        return value


class AskExplanationArgs(_Args):
    pass


class SubmitDiagnosisArgs(_Args):
    pass


SCHEMAS: dict[str, type[BaseModel]] = {
    "rank_probes": RankProbesArgs,
    "ask_probe": AskProbeArgs,
    "ask_explanation": AskExplanationArgs,
    "submit_diagnosis": SubmitDiagnosisArgs,
}


# --- definitions (constant, D8) ----------------------------------------------------------------------

def _definition(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required,
                       "additionalProperties": False}}}


_DEFINITIONS: list[dict] = json.loads(json.dumps([
    _definition("rank_probes",
                "Rank the probes not yet asked by expected information gain under the current belief. "
                "Read-only. Returns the top k with the misconceptions each targets, and the marginals.",
                {"k": {"type": "integer", "minimum": 1, "maximum": 8,
                       "description": "How many probes to return (default 3)."}}, []),
    _definition("ask_probe",
                "Show the student one probe program and record their predicted output and confidence. "
                "Updates the belief.",
                {"probe_id": {"type": "string", "pattern": r"^P\d{2}$",
                              "description": "A probe id such as P07 that has not been asked yet."}},
                ["probe_id"]),
    _definition("ask_explanation",
                "Ask the student to explain their answer to the last probe. The explanation is "
                "interpreted and, if informative, updates the belief.", {}, []),
    _definition("submit_diagnosis",
                "End the session with the current estimate. Accepted only when the belief is confident "
                "or the probe budget is spent.", {}, []),
]))


def tool_definitions() -> list[dict]:
    """The four tool definitions in fixed order (a copy, so callers cannot change the constant)."""
    return copy.deepcopy(_DEFINITIONS)


# --- helpers -------------------------------------------------------------------------------------------

def rounded(marginals: dict[str, float]) -> dict[str, float]:
    return {m: round(p, 4) for m, p in marginals.items()}


def _confident(session) -> bool:
    return session.belief.is_confident(session.config.low, session.config.high)


# --- executors (approved calls only) -----------------------------------------------------------------

@traceable(run_type="tool", name="rank_probes")
def rank_probes(session, args: RankProbesArgs) -> dict:
    k = args.k if args.k is not None else session.config.rank_k
    ranked = rank_by_gain(session.belief, session.unasked())[:k]
    return {"ranked": [{"probe_id": p.id, "expected_gain": round(g, 4), "targets": sorted(p.keys)}
                       for p, g in ranked],
            "marginals": rounded(session.belief.marginals()),
            "probes_used": len(session.asked), "probes_remaining": session.probes_remaining(),
            "confident": _confident(session)}


def answer_matches(probe, classified: str) -> list[str]:
    if classified == probe.correct:
        return ["correct"]
    matches = sorted(m for m, key in probe.keys.items() if key == classified)
    return matches or ["unexpected"]


@traceable(run_type="tool", name="ask_probe")
def ask_probe(session, args: AskProbeArgs) -> dict:
    probe = BY_ID[args.probe_id]
    config = session.config
    response = session.student.answer(probe)
    classified = probe.classify(strip_hedges(response.answer))
    session.belief.update(probe, classified, response.confidence if config.use_confidence else None,
                          config.slip_by_confidence)
    session.asked.append(probe.id)
    session.answers[probe.id] = response
    session.last_probe = probe.id
    return {"probe_id": probe.id, "code": probe.code, "answer": response.answer,
            "confidence": response.confidence, "classified": classified,
            "answer_matches": answer_matches(probe, classified),
            "marginals": rounded(session.belief.marginals()),
            "probes_remaining": session.probes_remaining(), "confident": _confident(session)}


@traceable(run_type="tool", name="ask_explanation")
def ask_explanation(session, args: AskExplanationArgs) -> dict:
    probe = BY_ID[session.last_probe]
    config = session.config
    last_answer = session.answers[probe.id].answer
    text = session.student.explain(probe)
    try:
        evidence = session.interpreter.label(probe, last_answer, text)
        valid, error = evidence.valid, evidence.error
    except Exception as exc:  # an interpreter failure is never terminal (specs/tools.md §2.3)
        evidence, valid, error = None, False, f"{type(exc).__name__}: {exc}"
    informative = bool(valid and evidence.informative)
    labels = sorted(evidence.labels) if valid else []
    # D27: score only the misconceptions the answer matched; a correct or unexpected answer scores all
    # of the probe's relevant misconceptions (specs/tools.md §2.3).
    matched = answer_matches(probe, probe.classify(strip_hedges(last_answer)))
    scored = [m for m in IDS if m in probe.keys and (m in matched or matched[0] in ("correct", "unexpected"))]
    applied = [m for m in labels if m in scored]
    ignored = [m for m in labels if m not in scored]
    if informative:
        session.belief.update_explanation(probe, applied, config.interpreter_sensitivity,
                                          config.interpreter_false_alarm, scope=scored)
    session.explained.add(probe.id)
    data = {"probe_id": probe.id, "explanation": text, "interpreter_valid": valid,
            "informative": informative, "belief_updated": informative, "scored": scored, "labels": labels,
            "applied_labels": applied, "ignored_labels": ignored,
            "marginals": rounded(session.belief.marginals()),
            "explanations_remaining": config.max_explanations - len(session.explained),
            "confident": _confident(session)}
    if not valid:
        data["interpreter_error"] = error or "interpreter failed"
    return data


@traceable(run_type="tool", name="submit_diagnosis")
def submit_diagnosis(session, args: SubmitDiagnosisArgs) -> dict:
    session.estimate = session.belief.estimate()
    session.outcome = "DIAGNOSED" if _confident(session) else "BUDGET"
    return {"estimate": session.estimate, "outcome": session.outcome}


EXECUTORS = {"rank_probes": rank_probes, "ask_probe": ask_probe,
             "ask_explanation": ask_explanation, "submit_diagnosis": submit_diagnosis}


def execute(session, tool: str, args: BaseModel) -> dict:
    """Run an approved call; returns the observation's data."""
    return EXECUTORS[tool](session, args)
