from pathlib import Path

from kelp_teaser.agents.sector_classifier import (
    SectorClassification,
    run as run_classifier,
)
from kelp_teaser.graph.state import GraphState
from kelp_teaser.schemas.plan import Sector
from tests.fixtures.stub_llm import patch_llm


def _state(brief: str) -> GraphState:
    return GraphState(company_name="Acme", input_path=Path("."), run_id="r1",
                      planner_brief=brief)


def test_sector_classifier_returns_sector_subsector_and_confidence(monkeypatch):
    obj = SectorClassification(sector=Sector.SaaS, sub_sector="DevOps tools",
                               confidence=0.92)
    patch_llm(monkeypatch, json_responses=[obj])
    result = run_classifier(_state("Acme is a SaaS company..."))
    assert result["sector"] == Sector.SaaS
    assert result["sub_sector"] == "DevOps tools"
    assert result["sector_confidence"] == 0.92


def test_sector_classifier_passes_dict_through_schema(monkeypatch):
    patch_llm(monkeypatch, json_responses=[
        {"sector": "D2C", "sub_sector": "Wellness", "confidence": 0.75},
    ])
    result = run_classifier(_state("Brief..."))
    assert result["sector"] == Sector.D2C
