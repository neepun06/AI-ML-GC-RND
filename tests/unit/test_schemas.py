import pytest
from pydantic import ValidationError

from kelp_teaser.schemas.facts import (
    SourceRef,
    Fact,
    IngestedDoc,
    WebSnippet,
    parse_source_id,
)


class TestSourceRef:
    def test_doc_source_id_roundtrip(self):
        ref = SourceRef(source_id="doc:annual_report.pdf#p12")
        assert ref.kind == "doc"
        assert ref.locator == "annual_report.pdf#p12"

    def test_web_source_id_roundtrip(self):
        ref = SourceRef(source_id="web:tavily:https://example.com/about")
        assert ref.kind == "web"
        assert ref.locator == "tavily:https://example.com/about"

    def test_image_source_id_roundtrip(self):
        ref = SourceRef(source_id="image:pexels:12345")
        assert ref.kind == "image"
        assert ref.locator == "pexels:12345"

    def test_invalid_source_id_rejected(self):
        with pytest.raises(ValidationError):
            SourceRef(source_id="not_a_valid_id")

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValidationError):
            SourceRef(source_id="phone:404:nothing")


class TestFact:
    def test_fact_requires_non_empty_source_id(self):
        with pytest.raises(ValidationError):
            Fact(value="some claim", source_id="", verbatim_quote="quote")

    def test_fact_requires_value(self):
        with pytest.raises(ValidationError):
            Fact(value="", source_id="doc:x.pdf#p1", verbatim_quote="quote")

    def test_fact_valid(self):
        f = Fact(
            value="Revenue ₹450 Cr in FY24",
            source_id="doc:annual_report.pdf#p12",
            verbatim_quote="Total revenue stood at ₹450 crore",
        )
        assert f.value == "Revenue ₹450 Cr in FY24"
        assert f.source_id == "doc:annual_report.pdf#p12"


class TestIngestedDoc:
    def test_ingested_doc_minimal(self):
        d = IngestedDoc(
            source_id="doc:report.pdf",
            filename="report.pdf",
            text="Lorem ipsum",
        )
        assert d.source_id == "doc:report.pdf"


class TestWebSnippet:
    def test_web_snippet_minimal(self):
        s = WebSnippet(
            source_id="web:tavily:https://x.com",
            url="https://x.com",
            summary="Bullet summary",
        )
        assert s.source_id == "web:tavily:https://x.com"


def test_parse_source_id_helper():
    assert parse_source_id("doc:a.pdf#p1") == ("doc", "a.pdf#p1")
    assert parse_source_id("web:tavily:https://x.com") == ("web", "tavily:https://x.com")


from kelp_teaser.schemas.plan import (
    Sector,
    ChartKind,
    ComponentKind,
    SectionPlan,
    SlidePlan,
    DeckPlan,
)


class TestSector:
    def test_known_sectors_exist(self):
        for name in [
            "Manufacturing",
            "SpecialtyChemicals",
            "D2C",
            "SaaS",
            "Pharma",
            "Logistics",
            "FinancialServices",
            "Consumer",
            "Other",
        ]:
            assert Sector(name) == getattr(Sector, name)


class TestSectionPlan:
    def test_chart_section_requires_chart_kind(self):
        with pytest.raises(ValidationError):
            SectionPlan(kind=ComponentKind.chart, data_hooks=["revenue"])

    def test_image_section_requires_image_brief(self):
        with pytest.raises(ValidationError):
            SectionPlan(kind=ComponentKind.hero_image, data_hooks=[])

    def test_metric_section_no_extra_fields_required(self):
        s = SectionPlan(kind=ComponentKind.metric_tile, data_hooks=["revenue_fy24"])
        assert s.kind == ComponentKind.metric_tile


class TestDeckPlan:
    def test_deck_must_have_exactly_three_slides(self):
        with pytest.raises(ValidationError):
            DeckPlan(
                codename="Project Halo",
                slides=[
                    SlidePlan(title="Slide 1", sections=[
                        SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["x"])
                    ])
                ],
            )

    def test_deck_codename_required(self):
        with pytest.raises(ValidationError):
            DeckPlan(codename="", slides=_three_minimal_slides())

    def test_deck_valid(self):
        plan = DeckPlan(codename="Project Halo", slides=_three_minimal_slides())
        assert plan.codename == "Project Halo"
        assert len(plan.slides) == 3


def _three_minimal_slides() -> list[SlidePlan]:
    return [
        SlidePlan(
            title=f"Slide {i + 1}",
            sections=[SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["x"])],
        )
        for i in range(3)
    ]


from kelp_teaser.schemas.slide import (
    Bullet,
    MetricTile,
    ChartSpec,
    ChartSeries,
    ComposedSection,
    ComposedSlide,
)


class TestComposedSection:
    def test_section_with_bullets_requires_each_bullet_to_have_source(self):
        with pytest.raises(ValidationError):
            ComposedSection(
                kind="bullet_list",
                bullets=[Bullet(text="some claim", source_id="")],
            )

    def test_section_with_metrics_requires_each_metric_to_have_source(self):
        with pytest.raises(ValidationError):
            ComposedSection(
                kind="metric_tile",
                metrics=[MetricTile(value="₹450 Cr", label="Revenue", source_id="")],
            )

    def test_valid_bullet_section_round_trips(self):
        section = ComposedSection(
            kind="bullet_list",
            bullets=[
                Bullet(text="5 facilities across western India", source_id="doc:report.pdf#p4"),
                Bullet(text="600+ active customers", source_id="web:tavily:https://x.com"),
            ],
        )
        assert len(section.bullets) == 2


class TestComposedSlide:
    def test_composed_slide_minimal(self):
        slide = ComposedSlide(
            index=0,
            title="Business Profile",
            sections=[
                ComposedSection(
                    kind="bullet_list",
                    bullets=[Bullet(text="A claim", source_id="doc:r.pdf#p1")],
                )
            ],
        )
        assert slide.index == 0

    def test_composed_slide_collects_all_source_ids(self):
        slide = ComposedSlide(
            index=1,
            title="Financials",
            sections=[
                ComposedSection(
                    kind="metric_tile",
                    metrics=[
                        MetricTile(value="₹450 Cr", label="Revenue FY24",
                                   source_id="doc:r.pdf#p12"),
                        MetricTile(value="22%", label="EBITDA Margin",
                                   source_id="doc:r.pdf#p14"),
                    ],
                ),
                ComposedSection(
                    kind="bullet_list",
                    bullets=[Bullet(text="X", source_id="web:tavily:https://x.com")],
                ),
            ],
        )
        ids = slide.all_source_ids()
        assert ids == {"doc:r.pdf#p12", "doc:r.pdf#p14", "web:tavily:https://x.com"}


class TestChartSpec:
    def test_chart_spec_requires_series(self):
        with pytest.raises(ValidationError):
            ChartSpec(
                chart_kind="revenue_growth_bar",
                title="Revenue",
                categories=["FY22", "FY23"],
                series=[],
                source_id="doc:r.pdf#p12",
            )

    def test_chart_spec_valid(self):
        c = ChartSpec(
            chart_kind="revenue_growth_bar",
            title="Revenue",
            categories=["FY22", "FY23", "FY24"],
            series=[ChartSeries(name="Revenue (₹ Cr)", values=[300, 380, 450])],
            source_id="doc:r.pdf#p12",
        )
        assert c.series[0].values == [300, 380, 450]


from kelp_teaser.schemas.critic import (
    CriticIssue,
    CriticReport,
    CriticSeverity,
    Substitution,
)
from kelp_teaser.schemas.citations import CitationRow, CitationTable


class TestCriticReport:
    def test_critic_issue_severity_enum(self):
        i = CriticIssue(
            slide_index=1,
            severity=CriticSeverity.blocking,
            category="source_validity",
            detail="Claim missing source",
        )
        assert i.severity == CriticSeverity.blocking

    def test_critic_report_groups_by_slide(self):
        report = CriticReport(
            issues=[
                CriticIssue(slide_index=0, severity=CriticSeverity.warning,
                            category="length", detail="bullet too long"),
                CriticIssue(slide_index=2, severity=CriticSeverity.blocking,
                            category="anonymization", detail="leaked name"),
            ],
        )
        assert report.issues_for_slide(0)[0].category == "length"
        assert report.has_blocking() is True


class TestSubstitution:
    def test_substitution_minimal(self):
        s = Substitution(original="Centum Electronics", replacement="Project Halo", slide_index=0)
        assert s.original == "Centum Electronics"


class TestCitationTable:
    def test_citation_row_minimal(self):
        row = CitationRow(
            slide_index=0,
            claim="Revenue ₹450 Cr",
            source_id="doc:r.pdf#p12",
            verbatim_quote="Total revenue stood at ₹450 crore",
            confidence="High",
        )
        assert row.slide_index == 0

    def test_citation_table_roundtrip(self):
        t = CitationTable(rows=[
            CitationRow(slide_index=0, claim="X", source_id="doc:r.pdf#p1",
                        verbatim_quote="X", confidence="High"),
        ])
        assert len(t.rows) == 1
