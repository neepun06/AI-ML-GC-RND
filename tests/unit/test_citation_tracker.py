from pathlib import Path

from kelp_teaser.agents.citation_tracker import run as run_tracker
from kelp_teaser.graph.state import GraphState
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.schemas.plan import ComponentKind
from kelp_teaser.schemas.slide import (
    Bullet, ComposedSection, ComposedSlide, MetricTile,
)


def test_citation_tracker_builds_one_row_per_claim():
    docs = [IngestedDoc(source_id="doc:x.md", filename="x.md",
                        text="Revenue ₹450 Cr in FY24.")]
    snippets = [WebSnippet(source_id="web:tavily:https://acme.com",
                           url="https://acme.com",
                           summary="600+ active customers.")]
    slide0 = ComposedSlide(index=0, title="Slide 1", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="600+ active customers globally", source_id="web:tavily:https://acme.com"),
        ]),
        ComposedSection(kind=ComponentKind.metric_tile, metrics=[
            MetricTile(value="₹450 Cr", label="Revenue FY24", source_id="doc:x.md"),
        ]),
    ])
    state = GraphState(company_name="Acme", input_path=Path("."), run_id="r1",
                       docs=docs, web_snippets=snippets,
                       composed_slides={0: slide0})

    result = run_tracker(state)
    table = result["citation_table"]
    assert len(table.rows) == 2
    claims = {row.claim for row in table.rows}
    assert "600+ active customers globally" in claims
    sources = {row.source_id for row in table.rows}
    assert "doc:x.md" in sources
    assert "web:tavily:https://acme.com" in sources


def test_citation_tracker_includes_chart_source():
    from kelp_teaser.schemas.plan import ChartKind
    from kelp_teaser.schemas.slide import ChartSeries, ChartSpec
    slide = ComposedSlide(index=0, title="t", sections=[
        ComposedSection(kind=ComponentKind.chart, chart=ChartSpec(
            chart_kind=ChartKind.revenue_growth_bar,
            title="Revenue",
            categories=["FY22", "FY23"],
            series=[ChartSeries(name="R", values=[1, 2])],
            source_id="doc:x.md",
        )),
    ])
    state = GraphState(company_name="Acme", input_path=Path("."), run_id="r1",
                       docs=[IngestedDoc(source_id="doc:x.md",
                                         filename="x.md", text="t")],
                       composed_slides={0: slide})
    table = run_tracker(state)["citation_table"]
    assert any(r.source_id == "doc:x.md" and "Revenue" in r.claim
               for r in table.rows)
