"""Citation-doc schemas."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from kelp_teaser.schemas.facts import parse_source_id


ConfidenceLevel = Literal["High", "Medium", "Low"]


class CitationRow(BaseModel):
    slide_index: int = Field(ge=0)
    claim: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    verbatim_quote: str = ""
    confidence: ConfidenceLevel = "Medium"

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        parse_source_id(v)
        return v


class CitationTable(BaseModel):
    rows: list[CitationRow] = Field(default_factory=list)
