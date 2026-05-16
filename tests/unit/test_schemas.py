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
