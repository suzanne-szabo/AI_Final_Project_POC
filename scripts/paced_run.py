"""Run `mm_agent.run` from a given code tree, pausing when the course key's hourly budget is spent.

The course gateway caps each key at a fixed spend per hour; a call over the cap fails with
"ExceededBudget". Counted as a model error, that would end the session with ERROR and spoil the run
(it did on 2026-11-15). This wrapper changes only the harness, never the agent:

- it wraps the two session functions (`run_interviewer_session`, `run_policy_session`) of the tree
  being run;
- a session whose trace mentions ExceededBudget is thrown away, the script waits, and the session is
  rerun from scratch with a fresh copy of the same student (same seed state), so a retried session is
  identical in conditions to a first attempt and its timings exclude the wait;
- it turns LangSmith tracing off (its free tier was used up), which never changes prompts or results.

Usage (from the revised repository; `--root` selects which code tree runs):

    uv run python scripts/paced_run.py --root . -- --deciders interviewer ... --out runs/NAME
    uv run python scripts/paced_run.py --root ../final_project_baseline -- --deciders ... --out runs/NAME

Waits are logged to stderr and to `<out>/budget_waits.jsonl`.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

BUDGET_MARKER = "ExceededBudget"


def budget_hit(result) -> bool:
    return BUDGET_MARKER in json.dumps(result.trace, default=str)


def paced(fn, wait_seconds: float, max_waits: int, log, sleep=time.sleep):
    """Wrap a session function: rerun a session that hit the budget cap, after a wait."""

    def wrapper(student, *args, **kwargs):
        try:
            original = copy.deepcopy(student)
        except Exception:  # a student that cannot be copied (live LLM client) is run once, unpaced
            return fn(student, *args, **kwargs)
        for attempt in range(max_waits + 1):
            fresh = copy.deepcopy(original)
            result = fn(fresh, *args, **kwargs)
            if not budget_hit(result) or attempt == max_waits:
                student.__dict__.update(fresh.__dict__)  # e.g. failure counters read by run.main
                return result
            log({"time": datetime.now().isoformat(timespec="seconds"), "student": getattr(student, "id", None),
                 "attempt": attempt + 1, "wait_seconds": wait_seconds})
            sleep(wait_seconds)
        return result  # not reached

    return wrapper


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, required=True, help="the code tree to run (revised or baseline)")
    parser.add_argument("--wait", type=float, default=600, help="seconds to wait after a budget error")
    parser.add_argument("--max-waits", type=int, default=36, help="waits per session before giving up")
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        i = argv.index("--")
        own, rest = argv[:i], argv[i + 1:]
    else:
        own, rest = argv, []
    args = parser.parse_args(own)
    root = args.root.resolve()

    os.environ["LANGSMITH_TRACING"] = "false"   # load_settings never overrides an existing variable
    os.chdir(root)
    sys.path.insert(0, str(root))
    import mm_agent.agent as agent_module
    import mm_agent.run as run_module

    out = None
    if "--out" in rest:
        out = Path(rest[rest.index("--out") + 1])
        out = out if out.is_absolute() else Path.cwd() / out

    def log(event: dict) -> None:
        print(f"[paced_run] budget cap reached: {event}", file=sys.stderr, flush=True)
        if out is not None:
            out.mkdir(parents=True, exist_ok=True)
            with (out / "budget_waits.jsonl").open("a") as fh:
                fh.write(json.dumps(event) + "\n")

    agent_module.run_interviewer_session = paced(agent_module.run_interviewer_session, args.wait,
                                                 args.max_waits, log)
    run_module.run_policy_session = paced(run_module.run_policy_session, args.wait, args.max_waits, log)
    return run_module.main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
