"""Compare chat models as the evidence interpreter on the labeled explanation sets. Live only.

    uv run python scripts/compare_models.py                         # both default models, both sets
    uv run python scripts/compare_models.py --models Qwen3.8-Flash-Next --repeat 2
    uv run python scripts/compare_models.py --cases data/explanations_vague.jsonl

For each model, every case in the case files (default: the clean set data/explanations.jsonl and the
vague set data/explanations_vague.jsonl) goes through mm_agent.interpret with the same cache-stable
prompt. Writes runs/models-<stamp>/<model>.jsonl (one record per call) and summary.md, with every
column reported separately per set: valid tool-call rate, exact label-set match, micro
precision/recall, false alarms on correct reasoning, agreement on `informative` (D23), false alarms on
non-informative explanations, latency, and cached prompt tokens (when the gateway reports them).
Cases run in file order and models run one after another, so from the second call on each model's
prompt prefix should already be cached.

`--summarize DIR` rebuilds summary.md from an existing run; records from runs before D25 (no `set` or
`informative` fields) count as clean and informative.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mm_agent.interpret import bind, interpret  # noqa: E402
from mm_agent.llm import MissingKeyError  # noqa: E402
from mm_agent.llm import make_model as _make_model  # noqa: E402
from mm_agent.probes import BY_ID  # noqa: E402

DEFAULT_MODELS = ["Qwen3.8-Flash-Next", "Gemma-4-26B-A4B"]
DEFAULT_CASES = [ROOT / "data" / "explanations.jsonl", ROOT / "data" / "explanations_vague.jsonl"]
SETS = ("clean", "vague")


def make_model(name: str):
    try:
        return _make_model(name)
    except MissingKeyError as error:
        raise SystemExit(str(error))


def set_name(path: Path) -> str:
    """`vague` for the vague test set (any file whose name mentions vague), else `clean`."""
    return "vague" if "vague" in path.stem else "clean"


def load_cases(path: Path) -> list[dict]:
    """Cases with their set name; a missing `informative` field means true (the clean set, D25)."""
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for case in cases:
        case.setdefault("informative", True)
        case["set"] = set_name(path)
    return cases


def with_defaults(record: dict) -> dict:
    """Old run records (before D25) count as clean and informative."""
    record = dict(record)
    record.setdefault("set", "clean")
    record.setdefault("informative_expected", True)
    record.setdefault("informative_predicted", True if record.get("valid") else None)
    return record


def summarize(records: list[dict]) -> dict:
    """Every column for each set present (keyed by set name)."""
    records = [with_defaults(r) for r in records]
    return {name: summarize_set(rs) for name in SETS
            if (rs := [r for r in records if r["set"] == name])}


def summarize_set(records: list[dict]) -> dict:
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
        "false_alarms_on_correct": sum(1 for r in valid if not r["labels"] and r["informative_expected"]
                                       and r["predicted"]),
        "correct_cases": sum(1 for r in records if not r["labels"] and r["informative_expected"]),
        "informative_agreement": (sum(r["informative_predicted"] == r["informative_expected"] for r in valid)
                                  / len(records)),
        "false_alarms_on_non_informative": sum(1 for r in valid if not r["informative_expected"] and r["predicted"]),
        "non_informative_cases": sum(1 for r in records if not r["informative_expected"]),
        "median_seconds": statistics.median(seconds),
        "max_seconds": max(seconds),
        "cache_reported": bool(reported),
        "cached_share": (sum(reported) / sum(p for c, p in zip(cached, prompt) if c is not None and p)
                         if reported and any(prompt) else None),
    }


def fmt(value, pattern="{:.2f}"):
    return "n/a" if value is None else pattern.format(value)


def write_summary(out: Path, summaries: dict) -> int:
    """summaries: model -> set name -> summary. One table per set."""
    lines = [f"# Interpreter model comparison {out.name}", "",
             "Labeled explanations x repeats per model, temperature 0, forced tool call. "
             "Columns are reported separately for each test set."]
    for set_ in SETS:
        rows = {name: s[set_] for name, s in summaries.items() if set_ in s}
        if not rows:
            continue
        calls = next(iter(rows.values()))["calls"]
        lines += ["", f"## {set_.capitalize()} set ({calls} calls per model)", "",
                  "| Model | Valid calls | Exact match | Precision | Recall | False alarms on correct reasoning "
                  "| Informative agreement | False alarms on non-informative | Median s | Max s "
                  "| Cached share of prompt |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, s in rows.items():
            lines.append(f"| {name} | {s['valid_rate']:.2f} | {s['exact_match']:.2f} | {fmt(s['precision'])} | "
                         f"{fmt(s['recall'])} | {s['false_alarms_on_correct']} of {s['correct_cases']} | "
                         f"{s['informative_agreement']:.2f} | {s['false_alarms_on_non_informative']} of "
                         f"{s['non_informative_cases']} | {s['median_seconds']:.1f} | {s['max_seconds']:.1f} | "
                         f"{fmt(s['cached_share'], '{:.0%}') if s['cache_reported'] else 'not reported'} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines) + f"\n\nWritten to {out}/")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--cases", type=Path, nargs="+", default=DEFAULT_CASES,
                        help="one or more case files (default: the clean and the vague set)")
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

    cases = [case for path in args.cases for case in load_cases(path)]
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
                record = {"model": name, "repeat": rep, "case_id": case["id"], "set": case["set"],
                          "labels": sorted(case["labels"]), "predicted": ev.labels, "valid": ev.valid,
                          "error": ev.error, "rationale": ev.rationale, "seconds": round(ev.seconds, 3),
                          "usage": ev.usage, "informative_expected": case["informative"],
                          "informative_predicted": ev.informative if ev.valid else None}
                records.append(record)
                ok = (ev.valid and set(ev.labels) == set(case["labels"])
                      and ev.informative == case["informative"])
                mark = "ok " if ok else "XX "
                print(f"  {mark}{case['set']} {case['id']} expected={case['labels']} got={ev.labels} "
                      f"informative={ev.informative if ev.valid else None} "
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
