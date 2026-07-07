from pathlib import Path

from kelp_teaser.agents.composer import build_source_context, compose_slide
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.schemas.plan import (
    ChartKind,
    ChartSpecSkeleton,
    ComponentKind,
    SectionPlan,
    SlidePlan,
)
from kelp_teaser.schemas.slide import (
    Bullet,
    ComposedSection,
    ComposedSlide,
    MetricTile,
)
from tests.fixtures.stub_llm import patch_llm


def test_build_source_context_includes_doc_text_and_snippet_summary():
    docs = [IngestedDoc(source_id="doc:x.md", filename="x.md",
                        text="Revenue ₹450 Cr.")]
    snippets = [WebSnippet(source_id="web:tavily:https://x.com",
                           url="https://x.com", summary="600+ customers.")]
    ctx = build_source_context(docs, snippets)
    assert "doc:x.md" in ctx
    assert "Revenue ₹450 Cr" in ctx
    assert "web:tavily:https://x.com" in ctx
    assert "600+ customers" in ctx


def test_compose_slide_returns_composed_slide(monkeypatch, tmp_path):
    docs = [IngestedDoc(source_id="doc:x.md", filename="x.md",
                        text="Revenue ₹450 Cr. 600+ customers.")]
    composed = ComposedSlide(index=0, title="Business Profile", sections=[
        ComposedSection(
            kind=ComponentKind.bullet_list,
            bullets=[
                Bullet(text="Mid-cap tech player", source_id="doc:x.md"),
                Bullet(text="600+ active customers", source_id="doc:x.md"),
            ],
        ),
    ])
    patch_llm(monkeypatch, json_responses=[composed])

    slide_plan = SlidePlan(title="Business Profile", sections=[
        SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["customer_count"]),
    ])

    out, _warnings = compose_slide(
        slide_index=0, slide_plan=slide_plan, codename="Project Halo",
        docs=docs, web_snippets=[],
        sector="SaaS", out_dir=tmp_path,
    )
    assert out.title == "Business Profile"
    assert out.sections[0].bullets[0].text.startswith("Mid-cap")


def test_compose_slide_returns_warning_when_chart_designer_fails(
    monkeypatch, tmp_path,
):
    """If a chart section was planned but ChartDesigner raises, compose_slide
    must surface a 'chart_missing' warning in its second return value
    rather than silently dropping the chart."""
    from kelp_teaser.agents import chart_designer

    def boom(plan_sec, *, source_context):
        raise RuntimeError("simulated ChartDesigner failure")

    monkeypatch.setattr(chart_designer, "design_chart", boom)

    docs = [IngestedDoc(source_id="doc:x.md", filename="x.md",
                        text="Revenue ₹450 Cr.")]
    composed = ComposedSlide(index=0, title="Financials", sections=[
        ComposedSection(
            kind=ComponentKind.chart,
            heading="Revenue",
            bullets=[],
            chart=None,  # Composer LLM left it unfilled
        ),
    ])
    patch_llm(monkeypatch, json_responses=[composed])

    slide_plan = SlidePlan(title="Financials", sections=[
        SectionPlan(
            kind=ComponentKind.chart,
            data_hooks=["revenue_fy24"],
            chart_spec=ChartSpecSkeleton(chart_kind=ChartKind.revenue_growth_bar),
        ),
    ])

    out, warnings = compose_slide(
        slide_index=0, slide_plan=slide_plan, codename="Project Halo",
        docs=docs, web_snippets=[],
        sector="SaaS", out_dir=tmp_path,
    )
    assert out.sections[0].chart is None
    assert any("chart_missing" in w for w in warnings)
    assert any("simulated ChartDesigner failure" in w for w in warnings)
