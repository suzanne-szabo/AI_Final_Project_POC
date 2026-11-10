"""LangSmith hooks (specs/agent.md §5, D14). A viewer only: never changes prompts or results.

- `traceable(**kwargs)` is `langsmith.traceable` when the package imports, else a no-op decorator.
  LangSmith sends nothing unless `LANGSMITH_TRACING` is set to true.
- `tracing_enabled()` reports whether `LANGSMITH_TRACING` is `true` or `1` (case-insensitive).
- `run_extra(metadata)` returns the keyword argument that attaches per-call metadata to a traced
  function (`langsmith_extra`), or nothing when LangSmith is not installed.
- `header_info()` is what the trace header records: on/off and the project name, never the key.

The JSONL trace stays the evidence record.
"""

from __future__ import annotations

import os

try:
    from langsmith import traceable as _langsmith_traceable
except ImportError:  # pragma: no cover - langsmith is installed with langchain-core
    _langsmith_traceable = None

DEFAULT_PROJECT = "mental-model-agent"


def traceable(**kwargs):
    """Decorator: `langsmith.traceable(**kwargs)` if available, otherwise return the function unchanged."""
    if _langsmith_traceable is None:
        def identity(func):
            return func
        return identity
    return _langsmith_traceable(**kwargs)


def tracing_enabled() -> bool:
    return os.environ.get("LANGSMITH_TRACING", "").strip().lower() in {"true", "1"}


def run_extra(metadata: dict) -> dict:
    """Keyword arguments that attach `metadata` to one call of a `traceable` function."""
    if _langsmith_traceable is None:
        return {}
    return {"langsmith_extra": {"metadata": metadata}}


def header_info() -> dict:
    enabled = tracing_enabled()
    project = (os.environ.get("LANGSMITH_PROJECT") or DEFAULT_PROJECT) if enabled else None
    return {"langsmith": enabled, "project": project}
