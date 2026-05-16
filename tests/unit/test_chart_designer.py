from kelp_teaser.agents.chart_designer import design_chart
from kelp_teaser.schemas.plan import ChartKind, ChartSpecSkeleton, ComponentKind, SectionPlan
from kelp_teaser.schemas.slide import ChartSeries, ChartSpec
from tests.fixtures.stub_llm import patch_llm


def _section() -> SectionPlan:
    return SectionPlan(
        kind=ComponentKind.chart,
        data_hooks=["revenue_fy22", "revenue_fy23", "revenue_fy24"],
        chart_spec=ChartSpecSkeleton(chart_kind=ChartKind.revenue_growth_bar, title=""),
        note="",
    )


def test_design_chart_returns_chart_spec(monkeypatch):
    expected = ChartSpec(
        chart_kind=ChartKind.revenue_growth_bar,
        title="Revenue (₹ Cr)",
        categories=["FY22", "FY23", "FY24"],
        series=[ChartSeries(name="Revenue", values=[300, 380, 450])],
        source_id="doc:r.md",
    )
    patch_llm(monkeypatch, json_responses=[expected])
    out = design_chart(_section(), source_context="doc:r.md — Revenue ₹300/380/450 Cr")
    assert out.chart_kind == ChartKind.revenue_growth_bar
    assert out.categories == ["FY22", "FY23", "FY24"]
    assert out.source_id == "doc:r.md"
