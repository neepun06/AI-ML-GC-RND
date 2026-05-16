"""Source-tracked fact schemas. Every claim on a slide is a Fact with a source_id."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SourceKind = Literal["doc", "web", "image"]
ALLOWED_KINDS: tuple[str, ...] = ("doc", "web", "image")


def parse_source_id(source_id: str) -> tuple[str, str]:
    """Split `kind:locator` into (kind, locator). Raises ValueError on malformed input."""
    if ":" not in source_id:
        raise ValueError(f"source_id missing ':' separator: {source_id!r}")
    kind, _, locator = source_id.partition(":")
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"unknown source kind {kind!r}; allowed: {ALLOWED_KINDS}")
    if not locator:
        raise ValueError(f"source_id has empty locator: {source_id!r}")
    return kind, locator


class SourceRef(BaseModel):
    """A reference to a single source document, web page, or image."""

    source_id: str = Field(min_length=1)

    @property
    def kind(self) -> str:
        return parse_source_id(self.source_id)[0]

    @property
    def locator(self) -> str:
        return parse_source_id(self.source_id)[1]

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        parse_source_id(v)  # raises ValueError on bad input
        return v


class Fact(BaseModel):
    """A textual claim plus the source it was extracted from."""

    value: str = Field(min_length=1, description="The claim as it will appear on the slide.")
    source_id: str = Field(min_length=1)
    verbatim_quote: str = Field(
        default="",
        description="Exact substring from the source supporting this claim.",
    )

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        parse_source_id(v)
        return v


class IngestedDoc(BaseModel):
    """A parsed private document from the data pack."""

    source_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    text: str = ""
    page_anchors: dict[str, str] = Field(
        default_factory=dict,
        description="Optional map of page/section labels to text chunks.",
    )

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        kind, _ = parse_source_id(v)
        if kind != "doc":
            raise ValueError(f"IngestedDoc source_id must start with 'doc:'; got {v!r}")
        return v


class WebSnippet(BaseModel):
    """A summarized search hit from the public web."""

    source_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    summary: str = ""
    query: str = ""

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        kind, _ = parse_source_id(v)
        if kind != "web":
            raise ValueError(f"WebSnippet source_id must start with 'web:'; got {v!r}")
        return v
