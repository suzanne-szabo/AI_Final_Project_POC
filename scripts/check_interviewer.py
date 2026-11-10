"""Check chat models as the interviewer on eight fixed scenarios (specs/agent.md §7, D16). Live only.

    uv run python scripts/check_interviewer.py                      # both default models
    uv run python scripts/check_interviewer.py --models Gemma-4-26B-A4B --repeat 2

Each scenario (S1-S8, built offline by mm_agent.check_scenarios) is the exact message list the
interviewer would be sent at one point of a session. The model makes one call; the scenario's
controller validates the call without executing it. Writes runs/interviewer-check-<stamp>/<model>.jsonl
(one record per call) and summary.md: valid single tool call rate, accepted rate, expected-action rate,
median latency and cached share of prompt tokens. Scenarios run in order and models one after another,
so from the second call on each model's prompt prefix (system prompt, opening, tools) should be cached.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mm_agent.agent import bind_interviewer, reply_calls  # noqa: E402
from mm_agent.check_scenarios import build_scenarios, state_problems  # noqa: E402
from mm_agent.controller import Approval  # noqa: E402
from mm_agent.interpret import cache_usage  # noqa: E402
from mm_agent.llm import MissingKeyError, make_model  # noqa: E402

DEFAULT_MODELS = ["Qwen3.8-Flash-Next", "Gemma-4-26B-A4B"]


def check_one(bound, scenario) -> dict:
    """One live call for one scenario; the reply is validated by the scenario's controller, never executed."""
    started = time.monotonic()
    try:
        reply = bound.invoke(scenario.messages)
    except Exception as error:  # recorded, not raised: the check must survive one failed call
        return {"tool": None, "args": None, "valid": False, "accepted": False, "expected": False,
                "error": f"MODEL_ERROR {type(error).__name__}: {error}",
                "seconds": round(time.monotonic() - started, 3), "usage": {}}
    seconds = time.monotonic() - started
    calls = reply_calls(reply)
    record = {"tool": calls[0]["name"] if calls else None, "args": calls[0]["args"] if calls else None,
              "calls": len(calls), "text": reply.content if isinstance(reply.content, str) else str(reply.content),
              "seconds": round(seconds, 3), "usage": cache_usage(reply), "error": None}
    record["valid"] = len(calls) == 1
    if calls:
        checked = scenario.controller.validate(calls[0]["name"], calls[0]["args"])
        record["accepted"] = isinstance(checked, Approval)
        record["policy"] = None if record["accepted"] else checked.policy
        record["message"] = None if record["accepted"] else checked.message
    else:
        record["accepted"] = False
    record["expected"] = bool(record["valid"] and scenario.expected(record["tool"], record["accepted"]))
    if scenario.name == "S1" and record["tool"] == "ask_probe" and isinstance(record["args"], dict):
        record["top_ranked"] = record["args"].get("probe_id") == scenario.top_probe
        record["expected"] = record["expected"] and record["top_ranked"]
    return record


def summarize(records: list[dict]) -> dict:
    seconds = [r["seconds"] for r in records]
    cached = [r["usage"].get("cached_tokens") for r in records]
    prompt = [r["usage"].get("input_tokens") for r in records]
    reported = [c for c in cached if c is not None]
    by_scenario: dict[str, list[bool]] = {}
    for r in records:
        by_scenario.setdefault(r["scenario"], []).append(r["expected"])
    return {
        "calls": len(records),
        "valid_rate": sum(r["valid"] for r in records) / len(records),
        "accepted_rate": sum(r["accepted"] for r in records) / len(records),
        "expected_rate": sum(r["expected"] for r in records) / len(records),
        "by_scenario": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(by_scenario.items())},
        "median_seconds": statistics.median(seconds),
        "max_seconds": max(seconds),
        "cache_reported": bool(reported),
        "cached_share": (sum(reported) / sum(p for c, p in zip(cached, prompt) if c is not None and p)
                         if reported and any(prompt) else None),
    }


def fmt(value, pattern="{:.2f}"):
    return "n/a" if value is None else pattern.format(value)


def write_summary(out: Path, summaries: dict) -> int:
    calls = next(iter(summaries.values()))["calls"]
    scenarios = list(next(iter(summaries.values()))["by_scenario"])
    lines = [f"# Interviewer model check {out.name}", "",
             f"{calls} calls per model (8 scenarios x repeats), temperature 0, forced single tool call.", "",
             "| Model | Valid single tool call | Accepted | Expected action | Median s | Max s | Cached share of prompt |",
             "|---|---|---|---|---|---|---|"]
    for name, s in summaries.items():
        lines.append(f"| {name} | {s['valid_rate']:.2f} | {s['accepted_rate']:.2f} | {s['expected_rate']:.2f} | "
                     f"{s['median_seconds']:.1f} | {s['max_seconds']:.1f} | "
                     f"{fmt(s['cached_share'], '{:.0%}') if s['cache_reported'] else 'not reported'} |")
    lines += ["", "Expected action per scenario:", "",
              "| Model | " + " | ".join(scenarios) + " |", "|---|" + "---|" * len(scenarios)]
    for name, s in summaries.items():
        lines.append(f"| {name} | " + " | ".join(s["by_scenario"].get(k, "-") for k in scenarios) + " |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines) + f"\n\nWritten to {out}/")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--repeat", type=int, default=1, help="run the eight scenarios this many times per model")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--summarize", type=Path, default=None,
                        help="rebuild summary.md from an existing run folder without calling any model")
    args = parser.parse_args()
    if args.summarize:
        return write_summary(args.summarize, {
            r[0]["model"]: summarize(r) for r in (
                [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
                for f in sorted(args.summarize.glob("*.jsonl")))})

    for scenario in build_scenarios():  # check every scenario's state before spending any model call
        problems = state_problems(scenario)
        if problems:
            raise SystemExit("Scenario check failed: " + "; ".join(problems))

    out = args.out or ROOT / "runs" / f"interviewer-check-{datetime.now():%Y-%m-%d_%H%M}"
    summaries = {}
    for name in args.models:
        try:
            bound = bind_interviewer(make_model(name))
        except MissingKeyError as error:
            raise SystemExit(str(error))
        out.mkdir(parents=True, exist_ok=True)
        records = []
        print(f"\n== {name} (8 scenarios x {args.repeat})")
        for rep in range(1, args.repeat + 1):
            for scenario in build_scenarios():  # fresh controllers: validation records a rejection
                record = {"model": name, "repeat": rep, "scenario": scenario.name,
                          "situation": scenario.situation, "expected_action": scenario.expected_text,
                          **check_one(bound, scenario)}
                records.append(record)
                mark = "ok " if record["expected"] else "XX "
                print(f"  {mark}{scenario.name} tool={record['tool']} args={record['args']} "
                      f"accepted={record['accepted']} {record['seconds']:.1f}s "
                      f"cached={record['usage'].get('cached_tokens')}"
                      + (f" ERROR {record['error']}" if record["error"] else ""))
        safe = name.replace("/", "_")
        with (out / f"{safe}.jsonl").open("w") as fh:
            for record in records:
                fh.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        summaries[name] = summarize(records)

    return write_summary(out, summaries)


if __name__ == "__main__":
    raise SystemExit(main())
