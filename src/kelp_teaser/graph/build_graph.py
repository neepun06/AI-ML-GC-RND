"""LangGraph topology for the v2 teaser pipeline.

Sequential: Ingestor → Researcher → SectorClassifier → Planner
Parallel fan-out (Send): 3 Composer instances, one per slide
Sequential: Anonymizer → Critic → CitationTracker → END
"""
from __future__ import annotations

import operator
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from kelp_teaser.agents import (
    anonymizer,
    citation_tracker,
    composer as composer_agent,
    critic,
    ingestor,
    planner,
    researcher,
    sector_classifier,
)
from kelp_teaser.graph.nodes import bind_node
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.slide import ComposedSlide


class _GraphDict(TypedDict, total=False):
    """LangGraph requires a TypedDict-shaped state with reducers per key.

    Most fields use the default replace-on-update. `composed_slides` uses dict-merge
    to support parallel fan-in.
    """
    company_name: str
    input_path: Path
    run_id: str
    docs: list
    web_snippets: list
    planner_brief: str
    sector: object
    sector_confidence: float | None
    sub_sector: str
    plan: object
    composed_slides: Annotated[dict[int, ComposedSlide], operator.or_]
    anonymization_log: list
    critic_report: object
    citation_table: object
    pptx_path: Path | None
    citations_path: Path | None
    trace_path: Path | None


def build_graph(*, trace_writer: TraceWriter | None = None,
                run_dir: Path | None = None):
    sg: StateGraph = StateGraph(_GraphDict)

    sg.add_node("ingestor", bind_node(ingestor.run, trace_writer=trace_writer))
    sg.add_node("researcher", bind_node(researcher.run, trace_writer=trace_writer))
    sg.add_node("sector_classifier",
                bind_node(sector_classifier.run, trace_writer=trace_writer))
    sg.add_node("planner", bind_node(planner.run, trace_writer=trace_writer))
    sg.add_node("composer", _composer_node_factory(trace_writer, run_dir))
    sg.add_node("anonymizer", bind_node(anonymizer.run, trace_writer=trace_writer))
    sg.add_node("critic", bind_node(critic.run, trace_writer=trace_writer))
    sg.add_node("citation_tracker",
                bind_node(citation_tracker.run, trace_writer=trace_writer))

    sg.add_edge(START, "ingestor")
    sg.add_edge("ingestor", "researcher")
    sg.add_edge("researcher", "sector_classifier")
    sg.add_edge("sector_classifier", "planner")
    sg.add_conditional_edges("planner", _fanout_to_composer, ["composer"])
    sg.add_edge("composer", "anonymizer")
    sg.add_edge("anonymizer", "critic")
    sg.add_edge("critic", "citation_tracker")
    sg.add_edge("citation_tracker", END)

    return sg.compile()


def _fanout_to_composer(state) -> list[Send]:
    """Emit one Send per slide in the plan. Each Send carries the full state
    plus a `_slide_index` injected via the partial state payload.
    """
    state_obj = GraphState.model_validate(state)
    if state_obj.plan is None:
        return []
    sends: list[Send] = []
    # Convert state to dict if it's a Pydantic model
    state_dict = state.model_dump() if hasattr(state, 'model_dump') else state
    for idx in range(len(state_obj.plan.slides)):
        sends.append(Send("composer", {**state_dict, "_slide_index": idx}))
    return sends


def _composer_node_factory(trace_writer: TraceWriter | None,
                            run_dir: Path | None):
    """A composer node that runs for ONE slide and returns {composed_slides: {idx: slide}}.

    LangGraph merges the returned dicts via the operator.or_ reducer on composed_slides.
    The `_slide_index` key is injected by `_fanout_to_composer` for each Send.

    `run_dir` is the per-run output folder so intermediate images land in tests'
    tmp_path rather than the repo's real data/outputs/.
    """
    _trace = trace_writer
    _run_dir = run_dir

    def composer_one(state) -> dict:
        idx: int = state.get("_slide_index", 0) if isinstance(state, dict) else 0
        state_obj = GraphState.model_validate({k: v for k, v in state.items()
                                                if k != "_slide_index"})
        if state_obj.plan is None:
            return {}
        slide_plan = state_obj.plan.slides[idx]
        out_dir = (_run_dir / "intermediate") if _run_dir is not None \
            else (Path("data/outputs") / state_obj.run_id / "intermediate")
        composed = composer_agent.compose_slide(
            slide_index=idx,
            slide_plan=slide_plan,
            codename=state_obj.plan.codename,
            docs=state_obj.docs,
            web_snippets=state_obj.web_snippets,
            sector=(state_obj.sector.value if state_obj.sector else "Other"),
            out_dir=out_dir,
        )
        if _trace is not None:
            _trace.write_step(f"composer_{idx}", composed.model_dump())
        return {"composed_slides": {idx: composed}}

    return composer_one
