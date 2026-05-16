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
