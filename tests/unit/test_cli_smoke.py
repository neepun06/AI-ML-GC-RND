from pathlib import Path

from kelp_teaser.cli import run_pipeline
from kelp_teaser.schemas.critic import CriticReport
from kelp_teaser.schemas.plan import (
    ChartKind, ChartSpecSkeleton, ComponentKind, DeckPlan, SectionPlan, SlidePlan,
)
from kelp_teaser.schemas.slide import Bullet, ComposedSection, ComposedSlide
from tests.fixtures.stub_llm import patch_llm


def _bullet_slide(idx: int) -> ComposedSlide:
    return ComposedSlide(index=idx, title=f"Slide {idx + 1}", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text=f"Project Halo fact {idx}",
                   source_id="doc:Ksolves-OnePager.md"),
        ]),
    ])


def test_run_pipeline_writes_pptx_and_citations(monkeypatch, tmp_path):
    monkeypatch.setattr("kelp_teaser.agents.researcher.web_search.search",
                        lambda query, max_results=5: [])

    plan = DeckPlan(codename="Project Halo", slides=[
        SlidePlan(title=f"Slide {i + 1}", sections=[
            SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["x"]),
        ]) for i in range(3)
    ])
    patch_llm(monkeypatch, json_responses=[
        {"sector": "SaaS", "sub_sector": "DevOps", "confidence": 0.9},
        plan,
        _bullet_slide(0), _bullet_slide(1), _bullet_slide(2),
        CriticReport(issues=[]),
    ])

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "Ksolves-OnePager.md").write_text("Mid-cap. 450 Cr.", encoding="utf-8")

    out_dir = tmp_path / "outputs"
    result = run_pipeline(
        company_name="Ksolves",
        input_path=input_dir,
        output_root=out_dir,
        run_id="rtest",
    )
    assert result.pptx_path is not None
    assert result.pptx_path.exists()
    assert result.citations_path is not None
    assert result.citations_path.exists()
    assert result.trace_path is not None
    assert result.trace_path.exists()
