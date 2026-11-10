"""Chat-model factory for the course gateway (architecture §5.5). Live only.

`make_model(model_name)` returns a `ChatOpenAI` client for the OpenAI-compatible course gateway with
`temperature=0`, `max_retries=0` (the callers own retries and record failures) and a 180 s timeout,
as in HW-09. Settings come from the environment or `.env` (`config.load_settings`). Offline code and
tests never call this; they pass the scripted fake chat model instead.
"""

from __future__ import annotations

from mm_agent.config import api_key_available, load_settings


class MissingKeyError(RuntimeError):
    """LLM_API_KEY is not set (or is still the .env.example placeholder)."""


def make_model(model_name: str):
    from langchain_openai import ChatOpenAI

    if not api_key_available():
        raise MissingKeyError("Set LLM_API_KEY in .env (see .env.example).")
    settings = load_settings()
    return ChatOpenAI(model=model_name, base_url=settings.base_url, api_key=settings.api_key,
                      temperature=0, max_retries=0, timeout=180)
