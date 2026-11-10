"""Scoring of finished sessions against their planted profiles (specs/agent.md §6).

The week-2 counterpart of `poc.score` (which stays in poc.py, unchanged, for the week-1 evidence run).
Per decider: exact profile match, Brier score, per-misconception precision and recall, mean probes and
explanations, the DIAGNOSED rate, the confident-but-wrong rate, error rates by kind, and for the LLM
interviewer: model calls per session, median latency, cached share of prompt tokens and rejections per
session.

Sessions that end without an estimate (ERROR, STEP_LIMIT) count as not matching; their Brier score uses
the last belief recorded in the trace (or the prior if no evidence was collected), so every session
contributes to every column.
"""

from __future__ import annotations

import statistics

from mm_agent.catalog import IDS
from mm_agent.controller import SessionResult


def final_marginals(result: SessionResult) -> dict[str, float]:
    """The estimate's marginals, else the last belief record's, else the configured prior."""
    if result.estimate is not None:
        return result.estimate["marginals"]
    beliefs = [r for r in result.trace if r["kind"] == "belief"]
    if beliefs:
        return beliefs[-1]["marginals"]
    prior = result.trace[0]["config"]["prior"]
    return {m: prior for m in IDS}


def diagnosis(result: SessionResult) -> set[str]:
    return set(result.estimate["most_likely"]) if result.estimate is not None else set()


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def model_stats(results: list[SessionResult]) -> dict:
    """Interviewer-only figures, from the counters and the `model` field of call records."""
    latencies, prompt, cached, cache_reported = [], 0, 0, False
    for r in results:
        for record in r.trace:
            if record["kind"] == "call" and "model" in record:
                latencies.append(record["model"]["seconds"])
                usage = record["model"].get("usage") or {}
                if usage.get("cached_tokens") is not None and usage.get("input_tokens"):
                    cache_reported = True
                    cached += usage["cached_tokens"]
                    prompt += usage["input_tokens"]
    n = len(results)
    return {"model_calls_per_session": sum(r.model_calls for r in results) / n,
            "median_latency": statistics.median(latencies) if latencies else None,
            "cached_share": _ratio(cached, prompt) if cache_reported else None,
            "rejections_per_session": sum(r.rejections_total for r in results) / n,
            "steps_per_session": sum(r.steps_used for r in results) / n}


def score(results: list[SessionResult]) -> dict:
    n = len(results)
    planted = [set(r.planted) for r in results]
    found = [diagnosis(r) for r in results]
    per = {}
    for m in IDS:
        tp = sum(m in p and m in d for p, d in zip(planted, found))
        fp = sum(m not in p and m in d for p, d in zip(planted, found))
        fn = sum(m in p and m not in d for p, d in zip(planted, found))
        per[m] = {"precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn), "support": tp + fn}
    brier = statistics.mean((final_marginals(r)[m] - (m in p)) ** 2 for r, p in zip(results, planted) for m in IDS)
    errors: dict[str, float] = {}
    for r in results:
        if r.terminal == "ERROR":
            errors[r.error_kind] = errors.get(r.error_kind, 0) + 1 / n
    summary = {
        "sessions": n,
        "exact_match": sum(p == d and r.estimate is not None for r, p, d in zip(results, planted, found)) / n,
        "brier": brier,
        "mean_probes": statistics.mean(r.probes_used for r in results),
        "mean_explanations": statistics.mean(r.explanations_used for r in results),
        "diagnosed_rate": sum(r.terminal == "DIAGNOSED" for r in results) / n,
        "budget_rate": sum(r.terminal == "BUDGET" for r in results) / n,
        "confident_wrong_rate": sum(r.terminal == "DIAGNOSED" and p != d
                                    for r, p, d in zip(results, planted, found)) / n,
        "step_limit_rate": sum(r.terminal == "STEP_LIMIT" for r in results) / n,
        "error_rate_by_kind": dict(sorted(errors.items())),
        "per_misconception": per,
    }
    if any(r.trace[0]["decider"] == "interviewer" for r in results):
        summary["interviewer"] = model_stats(results)
    return summary
