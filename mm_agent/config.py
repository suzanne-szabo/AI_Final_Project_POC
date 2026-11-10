"""Session configuration and gateway settings (specs/architecture.md §3).

`Config` is one frozen dataclass with a default for every field; it replaces week-1
`poc.SessionConfig` for week-2 sessions (poc.py keeps its own class so its evidence run reproduces).

`load_settings()` reads the course-gateway settings from the environment, after loading `.env` from
the project root. It is used only by live code paths (`llm.make_model`, the run command's checks);
nothing here is ever placed in a prompt (D8).
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "http://golem:4000/v1"
DEFAULT_INTERPRETER_MODEL = "Qwen3.8-Flash-Next"  # D12


def _default_slips() -> dict[int, float]:
    return {1: 0.35, 2: 0.20, 3: 0.10, 4: 0.06, 5: 0.04}


@dataclass(frozen=True)
class Config:
    max_probes: int = 10
    max_explanations: int = 5
    max_steps: int = 30
    max_consecutive_rejections: int = 3
    low: float = 0.15
    high: float = 0.85
    prior: float = 0.2
    model_slip: float = 0.10
    use_confidence: bool = True
    slip_by_confidence: dict[int, float] = field(default_factory=_default_slips)  # D19
    interpreter_sensitivity: float = 0.85  # D13
    interpreter_false_alarm: float = 0.05  # D13
    rank_k: int = 3

    def as_dict(self) -> dict:
        """All fields, JSON-ready (rating keys become strings, as json.dumps would make them)."""
        data = asdict(self)
        data["slip_by_confidence"] = {str(k): v for k, v in sorted(self.slip_by_confidence.items())}
        return data


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str


def load_settings() -> Settings:
    """Gateway settings from the environment; `.env` fills in only variables that are not set."""
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:  # python-dotenv is a dependency, but the offline code must not need it
        pass
    return Settings(base_url=os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL),
                    api_key=os.environ.get("LLM_API_KEY", ""))


def api_key_available() -> bool:
    """True when a real (non-placeholder) LLM_API_KEY is set."""
    key = load_settings().api_key.strip()
    return bool(key) and not key.startswith("your-")
