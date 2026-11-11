"""Batch run command: sessions for several deciders against the same simulated students (specs/agent.md §6).

    python -m mm_agent.run --deciders fixed shuffled eig eig_explain --students 50 --seed 7 --out runs/x
    python -m mm_agent.run --deciders eig_explain interviewer --interviewer-model Gemma-4-26B-A4B --students 5

Offline by default: `BankStudent` students and the `OracleInterpreter` (no network). The LLM interviewer,
`--interpreter llm` and `--student llm` call the course gateway and need `LLM_API_KEY` (`.env`).

Students and seeding follow week 1: profiles come from `random.Random(seed)` with `random_profile`,
for `sim-000`, `sim-001`, ...; each student's own rng is `random.Random(f"{seed}-{student_id}")` and the
oracle's is `random.Random(f"{seed}-{student_id}-oracle")`. Every decider faces freshly built,
identically seeded students.

Writes `DIR/<decider>_<student_id>.jsonl` (one trace per session), `DIR/summary.md`, `DIR/summary.json`
and `DIR/manifest.json`. `main(argv)` returns 0 on success and 2 (with a message) for invalid options.
"""

from __future__ import annotations

import mm_agent.config as config_module

import argparse
import json
import random
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from mm_agent.catalog import IDS
from mm_agent.config import DEFAULT_INTERPRETER_MODEL, ROOT, Config, api_key_available
from mm_agent.interpret import LLMInterpreter, OracleInterpreter
from mm_agent.policies import DECIDERS, run_policy_session
from mm_agent.scoring import score
from mm_agent.students import BankStudent, ExplanationBank, LLMStudent, random_profile
from mm_agent.tracing import header_info

ALL_DECIDERS = (*DECIDERS, "interviewer")
BANK_PATH = ROOT / "data" / "explanation_bank.jsonl"


class UsageError(Exception):
    """An invalid option or combination of options (exit code 2)."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m mm_agent.run", description=__doc__.splitlines()[0])
    parser.add_argument("--deciders", nargs="+", choices=ALL_DECIDERS, required=True)
    parser.add_argument("--students", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--rate", type=float, default=0.2, help="chance each misconception is planted")
    parser.add_argument("--student-slip", type=float, default=0.15)
    parser.add_argument("--student", choices=("bank", "llm"), default="bank")
    parser.add_argument("--confidence-mode", choices=("informative", "uninformative", "none"), default="informative")
    parser.add_argument("--no-use-confidence", action="store_true",
                        help="ignore confidence ratings in the answer likelihood (ablation, D19)")
    parser.add_argument("--vague-answer-rate", type=float, default=0.15)
    parser.add_argument("--interpreter", choices=("oracle", "llm", "none"), default="oracle")
    parser.add_argument("--interviewer-model", default=None)
    parser.add_argument("--interpreter-model", default=DEFAULT_INTERPRETER_MODEL)
    parser.add_argument("--student-model", default=None)
    parser.add_argument("--max-probes", type=int, default=10)
    parser.add_argument("--out", type=Path, default=None)
    return parser


def check_options(args) -> None:
    """The rejected combinations of specs/agent.md §6; raises UsageError with the reason."""
    deciders = set(args.deciders)
    if args.students < 1:
        raise UsageError("--students must be at least 1")
    if args.max_probes < 1:
        raise UsageError("--max-probes must be at least 1")
    if "interviewer" in deciders and not args.interviewer_model:
        raise UsageError("the interviewer decider needs --interviewer-model NAME")
    if deciders & {"eig_explain", "interviewer"} and args.interpreter == "none":
        raise UsageError("eig_explain and interviewer ask for explanations, so they need an interpreter "
                         "(--interpreter oracle or llm)")
    if args.student == "llm" and args.interpreter == "oracle":
        raise UsageError("--student llm cannot be used with --interpreter oracle: LLM-student explanations "
                         "are not in the bank (use --interpreter llm or none)")
    if args.student == "llm" and not args.student_model:
        raise UsageError("--student llm needs --student-model NAME")
    uses_llm = "interviewer" in deciders or args.interpreter == "llm" or args.student == "llm"
    if uses_llm and not api_key_available():
        raise UsageError("this run calls the course gateway: set LLM_API_KEY in .env (see .env.example)")


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def fmt(value, pattern: str = "{:.2f}") -> str:
    return "n/a" if value is None else pattern.format(value)


def summary_markdown(title: str, header: str, summary: dict) -> str:
    lines = [f"# Week-2 run {title}", "", header, "",
             "| Decider | Exact profile match | Brier (lower is better) | Mean probes | Mean explanations "
             "| Ended DIAGNOSED | Confident but wrong | Errors |",
             "|---|---|---|---|---|---|---|---|"]
    for decider, s in summary.items():
        errors = ", ".join(f"{k} {v:.2f}" for k, v in s["error_rate_by_kind"].items()) or "none"
        lines.append(f"| {decider} | {s['exact_match']:.2f} | {s['brier']:.3f} | {s['mean_probes']:.1f} | "
                     f"{s['mean_explanations']:.1f} | {s['diagnosed_rate']:.2f} | {s['confident_wrong_rate']:.2f} | "
                     f"{errors} |")
    deciders = list(summary)
    lines += ["", "Per misconception (precision / recall):", "",
              "| Misconception | " + " | ".join(deciders) + " | Support |",
              "|---|" + "---|" * len(deciders) + "---|"]
    for m in IDS:
        cells = [f"{fmt(summary[d]['per_misconception'][m]['precision'])} / "
                 f"{fmt(summary[d]['per_misconception'][m]['recall'])}" for d in deciders]
        support = summary[deciders[0]]["per_misconception"][m]["support"]
        lines.append(f"| {m} | " + " | ".join(cells) + f" | {support} |")
    if "interviewer" in summary and "interviewer" in summary["interviewer"]:
        s = summary["interviewer"]["interviewer"]
        lines += ["", "Interviewer:", "",
                  "| Model calls per session | Median latency s | Cached share of prompt | Rejections per session |",
                  "|---|---|---|---|",
                  f"| {s['model_calls_per_session']:.1f} | {fmt(s['median_latency'], '{:.1f}')} | "
                  f"{fmt(s['cached_share'], '{:.0%}')} | {s['rejections_per_session']:.2f} |"]
    failures = {d: s["student_failures"] for d, s in summary.items() if s.get("student_failures")}
    if failures:
        lines += ["", "LLM-student fallbacks (invalid replies): "
                  + ", ".join(f"{d} {n}" for d, n in failures.items())]
    return "\n".join(lines) + "\n"


def run(args, argv: list[str]) -> int:
    started = datetime.now()
    config = Config(max_probes=args.max_probes, use_confidence=not args.no_use_confidence)
    out = args.out or ROOT / "runs" / f"week2-{started:%Y-%m-%d_%H%M}"
    out.mkdir(parents=True, exist_ok=True)
    bank = ExplanationBank.load(BANK_PATH)
    rng = random.Random(args.seed)
    students = [(f"sim-{i:03d}", random_profile(rng, args.rate)) for i in range(args.students)]

    models = {"interviewer": args.interviewer_model if "interviewer" in args.deciders else None,
              "interpreter": args.interpreter_model if args.interpreter == "llm" else None,
              "student": args.student_model if args.student == "llm" else None}
    llm_interpreter = interviewer_model = None
    if args.interpreter == "llm" or "interviewer" in args.deciders or args.student == "llm":
        from mm_agent.llm import make_model  # live paths only

        if args.interpreter == "llm":
            llm_interpreter = LLMInterpreter(make_model(args.interpreter_model))
        if "interviewer" in args.deciders:
            interviewer_model = make_model(args.interviewer_model)

    def make_student(sid: str, profile: frozenset[str]):
        if args.student == "llm":
            from mm_agent.llm import make_model

            return LLMStudent(sid, profile, make_model(args.student_model))
        return BankStudent(sid, profile, args.student_slip, random.Random(f"{args.seed}-{sid}"), bank,
                           confidence_mode=args.confidence_mode, vague_answer_rate=args.vague_answer_rate)

    def make_interpreter(sid: str):
        if args.interpreter == "oracle":
            return OracleInterpreter(bank, config.interpreter_sensitivity, config.interpreter_false_alarm,
                                     random.Random(f"{args.seed}-{sid}-oracle"))
        return llm_interpreter  # None for --interpreter none

    summary = {}
    for decider in args.deciders:
        results, failures = [], 0
        for sid, profile in students:
            student = make_student(sid, profile)
            interpreter = make_interpreter(sid)
            if decider == "interviewer":
                from mm_agent.agent import run_interviewer_session

                result = run_interviewer_session(student, config, interviewer_model, interpreter,
                                                 session_id=sid, seed=args.seed,
                                            models={**models, "interviewer": None})
            else:
                result = run_policy_session(student, decider, config,
                                            interpreter=interpreter if decider == "eig_explain" else None,
                                            session_id=sid, seed=args.seed,
                                            models={**models, "interviewer": None})
            failures += getattr(student, "failures", 0)
            results.append(result)
            with (out / f"{decider}_{sid}.jsonl").open("w") as fh:
                for record in result.trace:
                    fh.write(json.dumps(record, sort_keys=True) + "\n")
        summary[decider] = score(results)
        if args.student == "llm":
            summary[decider]["student_failures"] = failures
        print(f"{decider}: exact {summary[decider]['exact_match']:.2f}, "
              f"Brier {summary[decider]['brier']:.3f}, mean probes {summary[decider]['mean_probes']:.1f}")

    header = (f"{args.students} simulated students ({args.student}), seed {args.seed}, plant rate {args.rate}, "
              f"student slip {args.student_slip}, confidence mode {args.confidence_mode} "
              f"(used: {config.use_confidence}), vague answer rate {args.vague_answer_rate}, "
              f"interpreter {args.interpreter}, budget {config.max_probes} probes / "
              f"{config.max_explanations} explanations.")
    (out / "summary.md").write_text(summary_markdown(out.name, header, summary))
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    manifest = {"command": "python -m mm_agent.run " + shlex.join(argv), "git_commit": git_commit(),
                "config": config.as_dict(), "models": models, "options": {k: str(v) if isinstance(v, Path) else v
                                                                          for k, v in vars(args).items()},
                "started": started.isoformat(timespec="seconds"),
                "ended": datetime.now().isoformat(timespec="seconds"), "tracing": header_info()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"\nTraces and summary written to {out}/")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    config_module.load_settings()   # read .env for every run, so LANGSMITH_* also apply offline (specs/agent.md §6)
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:  # argparse has printed its message; return instead of raising
        return int(stop.code or 0)
    try:
        check_options(args)
    except UsageError as error:
        print(f"{parser.prog}: error: {error}", file=sys.stderr)
        return 2
    return run(args, argv)


if __name__ == "__main__":
    raise SystemExit(main())
