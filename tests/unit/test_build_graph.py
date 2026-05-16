from pathlib import Path

from kelp_teaser.graph.build_graph import build_graph
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.critic import CriticReport
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.schemas.plan import (
    ChartKind, ChartSpecSkeleton, ComponentKind, DeckPlan, Sector,
    SectionPlan, SlidePlan,
)
from kelp_teaser.schemas.slide import (
    Bullet, ComposedSection, ComposedSlide,
)
from tests.fixtures.stub_llm import patch_llm


def _bullet_slide(idx: int, codename: str = "Project Halo") -> ComposedSlide:
    return ComposedSlide(index=idx, title=f"Slide {idx + 1}", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text=f"{codename} fact {idx}", source_id="doc:Ksolves-OnePager.md"),
        ]),
    ])


def test_graph_runs_end_to_end_with_stubbed_llm(monkeypatch, tmp_path):
    # Stub web_search to nothing (no Researcher LLM calls needed)
    monkeypatch.setattr("kelp_teaser.agents.researcher.web_search.search",
                        lambda query, max_results=5: [])

    plan = DeckPlan(codename="Project Halo", slides=[
        SlidePlan(title=f"Slide {i + 1}", sections=[
            SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["x"]),
        ]) for i in range(3)
    ])
    patch_llm(monkeypatch, json_responses=[
        # SectorClassifier
        {"sector": "SaaS", "sub_sector": "DevOps", "confidence": 0.9},
        # Planner
        plan,
        # 3 Composer calls
        _bullet_slide(0), _bullet_slide(1), _bullet_slide(2),
        # Critic
        CriticReport(issues=[]),
    ])

    # Prepare an input folder
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "Ksolves-OnePager.md").write_text("Mid-cap. Revenue 450 Cr. 600+ customers.", encoding="utf-8")

    state = GraphState(company_name="Ksolves", input_path=input_dir, run_id="rtest")
    graph = build_graph(trace_writer=TraceWriter(run_dir=None))
    final = graph.invoke(state)

    # final is a dict-like state. Pydantic re-validates via GraphState.
    final_state = GraphState.model_validate(final)
    assert final_state.plan is not None
    assert final_state.plan.codename == "Project Halo"
    assert len(final_state.composed_slides) == 3
    assert final_state.critic_report is not None
    assert final_state.citation_table is not None
    assert len(final_state.citation_table.rows) >= 3
