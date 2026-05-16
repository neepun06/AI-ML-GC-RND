"""SectorClassifier: single Flash call → Sector enum + sub_sector + confidence."""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.plan import Sector
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)


class SectorClassification(BaseModel):
    sector: Sector
    sub_sector: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    prompt = load_prompt("sector_classifier").render(brief=state.planner_brief)
    try:
        result = llm.complete_json(MODEL_FAST, prompt, SectorClassification)
    except Exception as e:  # noqa: BLE001
        log.error("SectorClassifier failed, defaulting to Other: %s", e)
        result = SectorClassification(sector=Sector.Other, confidence=0.0)

    if trace_writer is not None:
        trace_writer.write_step("sector_classifier", result.model_dump())

    return {
        "sector": result.sector,
        "sub_sector": result.sub_sector,
        "sector_confidence": result.confidence,
    }
