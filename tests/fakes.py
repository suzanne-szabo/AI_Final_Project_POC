"""Test doubles shared by the week-2 tests (no network)."""

from __future__ import annotations

import itertools

from langchain_core.messages import AIMessage

_ids = itertools.count(1)


def tool_call(name: str, args: dict | None = None, call_id: str | None = None) -> dict:
    return {"name": name, "args": args or {}, "id": call_id or f"call_{next(_ids)}", "type": "tool_call"}


def reply(*calls: dict, text: str = "") -> AIMessage:
    """An AIMessage carrying the given tool calls (none for a plain-text reply)."""
    return AIMessage(content=text, tool_calls=list(calls))


class ScriptedChatModel:
    """Fake chat model. Replies are returned in order; an Exception instance in the script is raised.

    Records every message list it was sent (`sent`) and every bind_tools call (`bound`).
    """

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent: list[list] = []
        self.bound: list[tuple] = []

    def bind_tools(self, tools, **kwargs):
        self.bound.append((tools, kwargs))
        return self

    def invoke(self, messages, *args, **kwargs):
        self.sent.append(list(messages))
        if not self.replies:
            raise AssertionError("ScriptedChatModel ran out of scripted replies")
        item = self.replies.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item
