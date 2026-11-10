"""The LangGraph interviewer loop (specs/agent.md §3).

    START -> llm -> controller --(call approved)--> tool -> continue? --(terminal)--> END
                        |                                     |
                        +--(no approved call: terminal?)------+--(otherwise)--> llm

- Graph state holds `messages` (the stored, append-only history), `pending` (the approved call and any
  extra calls of the same reply awaiting their P8 rejection) and `reply` (the model's latest reply,
  handed from the `llm` node to the `controller` node). The `Session` and `Controller` travel in
  LangGraph's run config, never in graph state.
- `llm` node: one step. Sends `[SystemMessage(SYSTEM_PROMPT), HumanMessage(OPENING)] + messages +
  [HumanMessage(status_message(...))]`; the status message is rebuilt every turn and never stored
  (D8). The model is bound once with the constant tool definitions, `tool_choice="required"` and
  `parallel_tool_calls=False`. One retry on an exception, then `record_model_error` (terminal).
- `controller` node: stores the AIMessage, records any text as a thought, handles a reply with no
  tool call (one reminder, then terminal), validates the first call. Every tool call id receives
  exactly one ToolMessage, in the order of the calls.
- `tool` node: executes the approved call, then rejects the reply's extra calls (P8).
- `continue?`: `check_terminal()`.

The application owns all state: the model's output only becomes tool calls the controller validates.
"""

from __future__ import annotations

import operator
import time
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from mm_agent.config import Config
from mm_agent.controller import Approval, Controller, Observation, SessionResult
from mm_agent.interpret import cache_usage
from mm_agent.prompts import OPENING, REMINDER, SYSTEM_PROMPT, status_message
from mm_agent.session import Session
from mm_agent.tools import tool_definitions
from mm_agent.tracing import run_extra, traceable


class GraphState(TypedDict, total=False):
    messages: Annotated[list, operator.add]  # append-only: nodes return only new messages
    pending: dict | None
    reply: AIMessage | None


def build_request(session: Session, controller: Controller, history: list) -> list:
    """The exact message list for one interviewer call: constant prefix, stored history, status last."""
    return ([SystemMessage(SYSTEM_PROMPT), HumanMessage(OPENING)] + list(history)
            + [HumanMessage(status_message(session, controller))])


def bind_interviewer(model):
    """Bind the interviewer tools identically for every call (D8)."""
    return model.bind_tools(tool_definitions(), tool_choice="required", parallel_tool_calls=False)


def tool_message(obs: Observation, call_id: str) -> ToolMessage:
    return ToolMessage(content=obs.to_json(), tool_call_id=call_id, name=obs.tool)


def text_of(message: AIMessage) -> str:
    """The text part of a reply (content may be a string or a list of content blocks)."""
    content = message.content
    if isinstance(content, str):
        return content.strip()
    parts = [b.get("text", "") if isinstance(b, dict) else str(b) for b in content or []]
    return "".join(parts).strip()


def reply_calls(message: AIMessage) -> list[dict]:
    """Tool calls in reply order; malformed calls (unparseable arguments) are kept so they get a P3."""
    calls = [{"name": c["name"], "args": c.get("args", {}), "id": c["id"]} for c in message.tool_calls or []]
    for bad in getattr(message, "invalid_tool_calls", None) or []:
        calls.append({"name": bad.get("name") or "", "args": bad.get("args"), "id": bad.get("id") or ""})
    return calls


def _parts(config: RunnableConfig) -> tuple[Session, Controller, Any]:
    c = config["configurable"]
    return c["session"], c["controller"], c["bound_model"]


def llm_node(state: GraphState, config: RunnableConfig) -> dict:
    session, controller, bound = _parts(config)
    controller.begin_step()
    request = build_request(session, controller, state.get("messages", []))
    error: BaseException | None = None
    for _ in range(2):  # one retry on an exception
        started = time.monotonic()
        try:
            reply = bound.invoke(request)
        except Exception as exc:
            controller.record_model_call(time.monotonic() - started, {})
            error = exc
            continue
        controller.record_model_call(time.monotonic() - started, cache_usage(reply))
        return {"reply": reply, "pending": None}
    controller.record_model_error(error)
    return {"reply": None, "pending": None}


def controller_node(state: GraphState, config: RunnableConfig) -> dict:
    session, controller, _ = _parts(config)
    reply = state.get("reply")
    if reply is None:  # the model call failed; the terminal reason is already recorded
        return {"pending": None}
    new: list = [reply]
    thought = text_of(reply)
    if thought:
        controller.record_thought(thought)
    calls = reply_calls(reply)
    if not calls:
        if controller.record_no_action() is not None:
            new.append(HumanMessage(REMINDER))
        return {"messages": new, "pending": None, "reply": None}
    first, extra = calls[0], calls[1:]
    checked = controller.validate(first["name"], first["args"])
    if isinstance(checked, Approval):
        return {"messages": new, "pending": {"approval": checked, "id": first["id"], "extra": extra},
                "reply": None}
    new.append(tool_message(checked, first["id"]))
    for call in extra:
        new.append(tool_message(controller.reject_extra_call(call["name"], call["args"]), call["id"]))
    return {"messages": new, "pending": None, "reply": None}


def tool_node(state: GraphState, config: RunnableConfig) -> dict:
    _, controller, _ = _parts(config)
    pending = state["pending"]
    new = [tool_message(controller.execute(pending["approval"]), pending["id"])]
    for call in pending["extra"]:
        new.append(tool_message(controller.reject_extra_call(call["name"], call["args"]), call["id"]))
    return {"messages": new, "pending": None}


def _after_controller(state: GraphState, config: RunnableConfig) -> str:
    if state.get("pending"):
        return "tool"
    return _continue(state, config)


def _continue(state: GraphState, config: RunnableConfig) -> str:
    _, controller, _ = _parts(config)
    return END if controller.check_terminal() is not None else "llm"


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("llm", llm_node)
    graph.add_node("controller", controller_node)
    graph.add_node("tool", tool_node)
    graph.add_edge(START, "llm")
    graph.add_edge("llm", "controller")
    graph.add_conditional_edges("controller", _after_controller, {"tool": "tool", "llm": "llm", END: END})
    graph.add_conditional_edges("tool", _continue, {"llm": "llm", END: END})
    return graph.compile()


GRAPH = build_graph()


def run_interviewer_session(student, config: Config, model, interpreter, session_id: str = "",
                            seed: int | None = None, models: dict[str, str | None] | None = None) -> SessionResult:
    """Run one LLM-interviewer session and return its result (trace included)."""
    metadata = {"session_id": session_id, "decider": "interviewer", "student_id": student.id}
    return _run_interviewer_session(student, config, model, interpreter, session_id, seed, models,
                                    **run_extra(metadata))


@traceable(run_type="chain", name="run_interviewer_session")
def _run_interviewer_session(student, config, model, interpreter, session_id, seed, models):
    session = Session.new(student, interpreter, config, session_id=session_id, decider="interviewer",
                          models=models, seed=seed)
    controller = Controller(session, "model")
    run_config = {"configurable": {"session": session, "controller": controller,
                                   "bound_model": bind_interviewer(model)},
                  "recursion_limit": 4 * config.max_steps + 10}
    GRAPH.invoke({"messages": [], "pending": None, "reply": None}, config=run_config)
    if controller.check_terminal() is None:  # cannot happen with the edges above; kept as a guard
        raise RuntimeError("interviewer graph ended without a terminal reason")
    return controller.result()
