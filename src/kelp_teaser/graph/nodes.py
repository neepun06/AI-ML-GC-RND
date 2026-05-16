"""Thin LangGraph node adapters: bind a TraceWriter to each agent's run()."""
from __future__ import annotations

from typing import Callable

from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter

AgentFn = Callable[..., dict]


def bind_node(agent_run: AgentFn, *, trace_writer: TraceWriter | None) -> Callable[[GraphState], dict]:
    def node(state: GraphState) -> dict:
        return agent_run(state, trace_writer=trace_writer)
    return node
