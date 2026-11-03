"""Code-only proof of concept: diagnose simulated students and write JSONL traces.

    python -m mm_agent.poc --students 50 --seed 1

For each simulated student, the adaptive policy (expected information gain) and the fixed-order
baseline each run a diagnostic session under the same probe budget. Each session is written as a
JSONL trace; summary.md compares the diagnoses with the planted profiles.

A session ends when every misconception's marginal is below `low` or above `high` (DIAGNOSED),
or when the probe budget is spent (BUDGET).
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mm_agent.belief import Belief
from mm_agent.catalog import IDS
from mm_agent.probes import BANK
from mm_agent.select import choose
from mm_agent.simstudent import SimStudent, random_profile


@dataclass(frozen=True)
class SessionConfig:
    max_probes: int = 10
    low: float = 0.15
    high: float = 0.85
    prior: float = 0.2
    model_slip: float = 0.1


@dataclass
class SessionResult:
    terminal: str
    diagnosis: frozenset[str]
    probes_used: int
    marginals: dict[str, float]
    records: list[dict]


def diagnose(student: SimStudent, policy: str, config: SessionConfig) -> SessionResult:
    belief = Belief(prior=config.prior, slip=config.model_slip)
    unused = list(BANK)
    records: list[dict] = [{
        "kind": "header", "student_id": student.id, "policy": policy,
        "planted": sorted(student.profile), "student_slip": student.slip,
        "config": config.__dict__,
    }]
    terminal = "BUDGET"
    for step in range(1, config.max_probes + 1):
        probe = choose(policy, belief, unused)
        unused.remove(probe)
        raw = student.answer(probe)
        option = probe.classify(raw)
        belief.update(probe, option)
        marginals = belief.marginals()
        records.append({"kind": "probe", "step": step, "probe_id": probe.id, "answer": raw, "classified": option})
        records.append({"kind": "belief", "step": step, "entropy": round(belief.entropy(), 4),
                        "marginals": {m: round(p, 4) for m, p in marginals.items()}})
        if all(p <= config.low or p >= config.high for p in marginals.values()):
            terminal = "DIAGNOSED"
            break
    marginals = belief.marginals()
    diagnosis = frozenset(m for m, p in marginals.items() if p > 0.5)
    records.append({"kind": "result", "terminal": terminal, "diagnosis": sorted(diagnosis),
                    "probes_used": step, "exact_match": diagnosis == student.profile})
    return SessionResult(terminal, diagnosis, step, marginals, records)


def score(results: list[tuple[frozenset[str], SessionResult]]) -> dict:
    exact = sum(r.diagnosis == planted for planted, r in results) / len(results)
    per = {}
    for m in IDS:
        tp = sum(m in planted and m in r.diagnosis for planted, r in results)
        fp = sum(m not in planted and m in r.diagnosis for planted, r in results)
        fn = sum(m in planted and m not in r.diagnosis for planted, r in results)
        per[m] = {"precision": tp / (tp + fp) if tp + fp else None,
                  "recall": tp / (tp + fn) if tp + fn else None, "support": tp + fn}
    brier = statistics.mean(
        (r.marginals[m] - (m in planted)) ** 2 for planted, r in results for m in IDS
    )
    return {"exact_match": exact, "brier": brier,
            "mean_probes": statistics.mean(r.probes_used for _, r in results),
            "diagnosed_rate": sum(r.terminal == "DIAGNOSED" for _, r in results) / len(results),
            "per_misconception": per}


def fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--students", type=int, default=50)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--rate", type=float, default=0.2, help="chance each misconception is planted")
    parser.add_argument("--student-slip", type=float, default=0.1)
    parser.add_argument("--max-probes", type=int, default=10)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    config = SessionConfig(max_probes=args.max_probes)
    out = args.out or Path("runs") / f"poc-{datetime.now():%Y-%m-%d_%H%M}"
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    students = [(f"sim-{i:03d}", random_profile(rng, args.rate)) for i in range(args.students)]

    summary = {}
    for policy in ("eig", "fixed"):
        results = []
        for sid, profile in students:
            # Same slip sequence for both policies: seed from the student, not the policy.
            student = SimStudent(sid, profile, args.student_slip, random.Random(f"{args.seed}-{sid}"))
            result = diagnose(student, policy, config)
            results.append((profile, result))
            with (out / f"{policy}_{sid}.jsonl").open("w") as fh:
                for record in result.records:
                    fh.write(json.dumps(record, sort_keys=True) + "\n")
        summary[policy] = score(results)

    lines = [f"# PoC run {out.name}", "",
             f"{args.students} simulated students, seed {args.seed}, plant rate {args.rate}, "
             f"student slip {args.student_slip}, model slip {config.model_slip}, budget {config.max_probes} probes.",
             "", "| Policy | Exact profile match | Brier (lower is better) | Mean probes | Ended DIAGNOSED |",
             "|---|---|---|---|---|"]
    for policy, s in summary.items():
        lines.append(f"| {policy} | {s['exact_match']:.2f} | {s['brier']:.3f} | {s['mean_probes']:.1f} | "
                     f"{s['diagnosed_rate']:.2f} |")
    lines += ["", "Per misconception (precision / recall, support):", "",
              "| Misconception | eig | fixed | Support |", "|---|---|---|---|"]
    for m in IDS:
        e, f = summary["eig"]["per_misconception"][m], summary["fixed"]["per_misconception"][m]
        lines.append(f"| {m} | {fmt(e['precision'])} / {fmt(e['recall'])} | "
                     f"{fmt(f['precision'])} / {fmt(f['recall'])} | {e['support']} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    print("\n".join(lines))
    print(f"\nTraces and summary written to {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
