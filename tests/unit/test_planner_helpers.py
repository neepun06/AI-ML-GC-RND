from pathlib import Path

from kelp_teaser.agents.planner import run as run_planner
from kelp_teaser.graph.state import GraphState
from kelp_teaser.schemas.plan import (
    ChartKind,
    ComponentKind,
    DeckPlan,
    Sector,
    SectionPlan,
    SlidePlan,
    ChartSpecSkeleton,
)
from tests.fixtures.stub_llm import patch_llm


def _state() -> GraphState:
    return GraphState(company_name="Ksolves", input_path=Path("."), run_id="r1",
                      planner_brief="Brief...", sector=Sector.SaaS,
                      sub_sector="DevOps")


def _valid_plan() -> DeckPlan:
    return DeckPlan(codename="Project Halo", slides=[
        SlidePlan(title="Overview", sections=[
            SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["summary"]),
        ]),
        SlidePlan(title="Financials", sections=[
            SectionPlan(kind=ComponentKind.chart, data_hooks=["revenue"],
                        chart_spec=ChartSpecSkeleton(chart_kind=ChartKind.revenue_growth_bar)),
        ]),
        SlidePlan(title="Thesis", sections=[
            SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["hooks"]),
        ]),
    ])


def test_planner_returns_deck_plan(monkeypatch):
    plan = _valid_plan()
    patch_llm(monkeypatch, json_responses=[plan])
    result = run_planner(_state())
    assert result["plan"].codename == "Project Halo"
    assert len(result["plan"].slides) == 3


def test_planner_renders_prompt_with_sector(monkeypatch):
    captured = {}

    def fake_complete_json(model, prompt, schema, *, temperature=0.2, tracker=None):
        captured["prompt"] = prompt
        return _valid_plan()

    import kelp_teaser.tools.llm as llm_module
    monkeypatch.setattr(llm_module, "complete_json", fake_complete_json)

    run_planner(_state())
    assert "SaaS" in captured["prompt"]
    assert "DevOps" in captured["prompt"]


def test_planner_surfaces_identifier_terms(monkeypatch):
    """The planner node must copy DeckPlan.identifier_terms onto the
    returned state dict so the Anonymizer can consume them."""
    plan = _valid_plan().model_copy(update={
        "identifier_terms": ["Dashboard Ninja", "NASSCOM Impact Award"],
    })
    patch_llm(monkeypatch, json_responses=[plan])
    result = run_planner(_state())
    assert result["identifier_terms"] == ["Dashboard Ninja", "NASSCOM Impact Award"]
