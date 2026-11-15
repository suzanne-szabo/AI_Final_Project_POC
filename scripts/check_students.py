"""Fidelity check for LLM students (D35; docs/student-simulator-plan.md §3.1). Live: needs the gateway.

Each LLM student gets all 15 probes with no interviewer; every answer is compared with the answer its
planted profile predicts. Start small:

    uv run python scripts/check_students.py --model Gemma-4-26B-A4B --n 4

then the full set (12 students, about 180 answer calls, plus explanations with --explain):

    uv run python scripts/check_students.py --model Gemma-4-26B-A4B --explain

Writes runs/students-check-<timestamp>/: records.jsonl (one scored answer per line, with the explanation
when asked), summary.json, summary.md, manifest.json.

Prompt cache (D8): every student shares the constant system prompt and tool list; each student's
history is append-only. The summary reports the cached share of prompt tokens when the gateway reports
it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mm_agent.config import load_settings  # noqa: E402
from mm_agent.fidelity import DEFAULT_PROFILES, as_dict, run_student, summarize  # noqa: E402
from mm_agent.students import STYLES, LLMStudent  # noqa: E402

STYLE_CYCLE = ("clear", "terse", "hedging")


def short(profile) -> str:
    return "+".join(m.split("_")[0] for m in sorted(profile)) or "none"


def write_summary(out: Path, summary: dict, meta: dict) -> None:
    s = summary
    pct = lambda v: "n/a" if v is None else f"{v:.0%}"  # noqa: E731
    lines = [f"# LLM-student fidelity check: {meta['model']}", "",
             f"{meta['students']} students, style {meta['style']}, {s['answers']} answers "
             f"({s['belief_answers']} on belief probes, {s['neutral_answers']} neutral). "
             f"Model calls {meta['calls']}, fallbacks {meta['failures']}, "
             f"cached share of prompt tokens {pct(meta['cached_share'])}.", "",
             "| Measure | Value | Direction |", "|---|---|---|",
             f"| Belief fidelity (predicted wrong answer given) | {pct(s['belief_fidelity'])} | higher is better |",
             f"| Leak rate (correct answer despite the belief) | {pct(s['leak_rate'])} | lower is better |",
             f"| Unexpected on belief probes | {pct(s['belief_unexpected_rate'])} | lower is better |",
             f"| Other misconception's answer | {pct(s['other_key_rate'])} | lower is better |",
             f"| Neutral accuracy (correct where beliefs agree with Python) | {pct(s['neutral_accuracy'])} | higher is better |",
             f"| Invented misconception answers | {pct(s['invented_rate'])} | lower is better |",
             f"| Mean confidence: faithful belief answers / leaks / neutral | "
             f"{s['mean_confidence_faithful_belief']} / {s['mean_confidence_leak']} / {s['mean_confidence_neutral']} | |",
             "", "Per misconception (belief probes it decides):", "",
             "| Misconception | Answers | Fidelity | Leak | Unexpected |", "|---|---|---|---|---|"]
    for m, v in s["per_misconception"].items():
        lines.append(f"| {m} | {v['answers']} | {pct(v['fidelity'])} | {pct(v['leak'])} | {pct(v['unexpected'])} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, help="the model that plays the students")
    parser.add_argument("--n", type=int, default=len(DEFAULT_PROFILES),
                        help=f"use the first N of the {len(DEFAULT_PROFILES)} default profiles")
    parser.add_argument("--style", choices=(*STYLES, "cycle", "none"), default="clear",
                        help="'cycle' rotates clear, terse, hedging across students")
    parser.add_argument("--explain", action="store_true", help="also ask for an explanation on belief probes")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    load_settings()
    from mm_agent.llm import make_model

    out = args.out or ROOT / "runs" / f"students-check-{datetime.now():%Y-%m-%d_%H%M}"
    out.mkdir(parents=True, exist_ok=False)
    model = make_model(args.model)  # one client; each student binds the same constant tools
    started = datetime.now().isoformat(timespec="seconds")
    records, rows, calls, failures, usage = [], [], 0, 0, []
    for i, profile in enumerate(DEFAULT_PROFILES[:args.n]):
        style = (STYLE_CYCLE[i % 3] if args.style == "cycle" else None if args.style == "none" else args.style)
        student = LLMStudent(f"llm-{i:02d}-{short(profile)}", profile, model, style=style)
        t0 = time.monotonic()
        scored, explanations = run_student(student, explain=args.explain)
        calls, failures, usage = calls + student.calls, failures + student.failures, usage + student.usage
        faithful = sum(r.outcome == "faithful" for r in scored)
        print(f"{student.id:<22} style={style or '-':<8} faithful {faithful}/{len(scored)} "
              f"leaks {sum(r.outcome == 'leak' for r in scored)} ({time.monotonic() - t0:.0f} s)", flush=True)
        records += scored
        for r in scored:
            row = as_dict(r)
            row["explanation"] = explanations.get(r.probe_id)
            rows.append(row)
    prompt = sum(u.get("input_tokens") or 0 for u in usage)
    cached = [u.get("cached_tokens") for u in usage if u.get("cached_tokens") is not None]
    summary = summarize(records)
    try:
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                                text=True).stdout.strip() or None
    except OSError:
        commit = None
    meta = {"command": " ".join(["python", *sys.argv]), "git_commit": commit, "model": args.model,
            "students": args.n, "style": args.style, "explain": args.explain, "started": started,
            "ended": datetime.now().isoformat(timespec="seconds"), "calls": calls, "failures": failures,
            "prompt_tokens": prompt,
            "cached_share": round(sum(cached) / prompt, 3) if cached and prompt else None}
    with (out / "records.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    (out / "summary.json").write_text(json.dumps({"summary": summary, "meta": meta}, indent=2, sort_keys=True))
    (out / "manifest.json").write_text(json.dumps(meta, indent=2, sort_keys=True))
    write_summary(out, summary, meta)
    print((out / "summary.md").read_text())
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
