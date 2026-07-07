"""Planner: Pro call returning a DeckPlan with codename + 3 SlidePlans."""
from __future__ import annotations

import logging

from kelp_teaser.config import MODEL_SMART
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.plan import DeckPlan
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    sector_name = state.sector.value if state.sector is not None else "Other"
    prompt = load_prompt("planner").render(
        sector=sector_name,
        sub_sector=state.sub_sector,
        brief=state.planner_brief,
    )
    plan: DeckPlan = llm.complete_json(MODEL_SMART, prompt, DeckPlan)

    if trace_writer is not None:
        trace_writer.write_step("planner", plan.model_dump())

    return {"plan": plan, "identifier_terms": plan.identifier_terms}
