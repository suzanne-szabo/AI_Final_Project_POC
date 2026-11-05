"""Compare chat models as the evidence interpreter on the labeled explanation set. Live only.

    uv run python scripts/compare_models.py                         # both default models
    uv run python scripts/compare_models.py --models Qwen3.8-Flash-Next --repeat 2

For each model, every case in data/explanations.jsonl goes through mm_agent.interpret with the same
cache-stable prompt. Writes runs/models-<stamp>/<model>.jsonl (one record per call) and summary.md:
valid tool-call rate, exact label-set match, micro precision/recall, latency, and cached prompt
tokens (when the gateway reports them). Cases run in file order and models run one after another,
so from the second call on each model's prompt prefix should already be cached.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mm_agent.interpret import bind, interpret  # noqa: E402
from mm_agent.probes import BY_ID  # noqa: E402

DEFAULT_MODELS = ["Qwen3.8-Flash-Next", "Gemma-4-26B-A4B"]
DEFAULT_BASE_URL = "http://golem:4000/v1"


def make_model(name: str):
    from dotenv import load_dotenv
    from langchain_openai import ChatOpenAI

    load_dotenv(ROOT / ".env")
    key = os.environ.get("LLM_API_KEY", "")
    if not key or key.startswith("your-"):
        raise SystemExit("Set LLM_API_KEY in .env (see .env.example).")
    return ChatOpenAI(model=name, base_url=os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL), api_key=key,
                      temperature=0, max_retries=0, timeout=180)


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summarize(records: list[dict]) -> dict:
    valid = [r for r in records if r["valid"]]
    tp = sum(len(set(r["predicted"]) & set(r["labels"])) for r in valid)
    fp = sum(len(set(r["predicted"]) - set(r["labels"])) for r in valid)
    fn = sum(len(set(r["labels"]) - set(r["predicted"])) for r in valid)
    seconds = [r["seconds"] for r in records]
    cached = [r["usage"].get("cached_tokens") for r in records]
    prompt = [r["usage"].get("input_tokens") for r in records]
    reported = [c for c in cached if c is not None]
    return {
        "calls": len(records),
        "valid_rate": len(valid) / len(records),
        "exact_match": sum(set(r["predicted"]) == set(r["labels"]) for r in valid) / len(records),
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "false_alarms_on_correct": sum(1 for r in valid if not r["labels"] and r["predicted"]),
        "correct_cases": sum(1 for r in records if not r["labels"]),
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
    lines = [f"# Interpreter model comparison {out.name}", "",
             f"{calls} calls per model (labeled explanations x repeats), temperature 0, forced tool call.", "",
             "| Model | Valid calls | Exact match | Precision | Recall | False alarms on correct reasoning "
             "| Median s | Max s | Cached share of prompt |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, s in summaries.items():
        lines.append(f"| {name} | {s['valid_rate']:.2f} | {s['exact_match']:.2f} | {fmt(s['precision'])} | "
                     f"{fmt(s['recall'])} | {s['false_alarms_on_correct']} of {s['correct_cases']} | "
                     f"{s['median_seconds']:.1f} | {s['max_seconds']:.1f} | "
                     f"{fmt(s['cached_share'], '{:.0%}') if s['cache_reported'] else 'not reported'} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines) + f"\n\nWritten to {out}/")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--cases", type=Path, default=ROOT / "data" / "explanations.jsonl")
    parser.add_argument("--repeat", type=int, default=1, help="run the case set this many times per model")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--summarize", type=Path, default=None,
                        help="rebuild summary.md from an existing run folder without calling any model")
    args = parser.parse_args()
    if args.summarize:
        return write_summary(args.summarize, {
            r[0]["model"]: summarize(r) for r in (
                [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
                for f in sorted(args.summarize.glob("*.jsonl")))})

    cases = load_cases(args.cases)
    out = args.out or ROOT / "runs" / f"models-{datetime.now():%Y-%m-%d_%H%M}"
    out.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for name in args.models:
        bound = bind(make_model(name))
        records = []
        print(f"\n== {name} ({len(cases)} cases x {args.repeat})")
        for rep in range(1, args.repeat + 1):
            for case in cases:
                ev = interpret(bound, BY_ID[case["probe_id"]], case["answer"], case["explanation"])
                record = {"model": name, "repeat": rep, "case_id": case["id"], "labels": sorted(case["labels"]),
                          "predicted": ev.labels, "valid": ev.valid, "error": ev.error,
                          "rationale": ev.rationale, "seconds": round(ev.seconds, 3), "usage": ev.usage}
                records.append(record)
                mark = "ok " if ev.valid and set(ev.labels) == set(case["labels"]) else "XX "
                print(f"  {mark}{case['id']} expected={case['labels']} got={ev.labels} "
                      f"{ev.seconds:.1f}s cached={ev.usage.get('cached_tokens')}"
                      + (f" ERROR {ev.error}" if ev.error else ""))
        safe = name.replace("/", "_")
        with (out / f"{safe}.jsonl").open("w") as fh:
            for record in records:
                fh.write(json.dumps(record, sort_keys=True) + "\n")
        summaries[name] = summarize(records)

    return write_summary(out, summaries)


if __name__ == "__main__":
    raise SystemExit(main())
