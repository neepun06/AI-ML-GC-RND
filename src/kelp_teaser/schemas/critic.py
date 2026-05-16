"""Critic and anonymization schemas."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CriticSeverity(str, Enum):
    info = "info"
    warning = "warning"
    blocking = "blocking"


class CriticIssue(BaseModel):
    slide_index: int = Field(ge=0)
    severity: CriticSeverity
    category: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    suggested_fix: str = ""


class CriticReport(BaseModel):
    issues: list[CriticIssue] = Field(default_factory=list)

    def issues_for_slide(self, idx: int) -> list[CriticIssue]:
        return [i for i in self.issues if i.slide_index == idx]

    def has_blocking(self) -> bool:
        return any(i.severity == CriticSeverity.blocking for i in self.issues)


class Substitution(BaseModel):
    original: str = Field(min_length=1)
    replacement: str = Field(min_length=1)
    slide_index: int = Field(ge=0)
    reason: str = ""
