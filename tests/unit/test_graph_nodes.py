from pathlib import Path

from kelp_teaser.graph.nodes import bind_node
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter


def test_bind_node_injects_trace_writer():
    captured = {}

    def fake_agent(state, *, trace_writer=None):
        captured["trace_writer"] = trace_writer
        return {"company_name": state.company_name}

    writer = TraceWriter(run_dir=None)
    node = bind_node(fake_agent, trace_writer=writer)
    out = node(GraphState(company_name="Acme", input_path=Path("."), run_id="r1"))
    assert captured["trace_writer"] is writer
    assert out == {"company_name": "Acme"}
