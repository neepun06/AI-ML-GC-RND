"""GraphState: the single Pydantic object passed through every LangGraph node."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from kelp_teaser.schemas.citations import CitationTable
from kelp_teaser.schemas.critic import CriticReport, Substitution
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.schemas.plan import DeckPlan, Sector
from kelp_teaser.schemas.slide import ComposedSlide


class GraphState(BaseModel):
    # Input (set by CLI before the graph runs)
    company_name: str = Field(min_length=1)
    input_path: Path
    run_id: str = Field(min_length=1)

    # Filled by Ingestor / Researcher
    docs: list[IngestedDoc] = Field(default_factory=list)
    web_snippets: list[WebSnippet] = Field(default_factory=list)
    planner_brief: str = ""

    # Filled by SectorClassifier
    sector: Sector | None = None
    sector_confidence: float | None = None
    sub_sector: str = ""

    # Filled by Planner
    plan: DeckPlan | None = None

    # Filled by Composer (parallel fan-in via dict-merge)
    composed_slides: dict[int, ComposedSlide] = Field(default_factory=dict)

    # Filled by Anonymizer
    anonymization_log: list[Substitution] = Field(default_factory=list)
    identifier_terms: list[str] = Field(
        default_factory=list,
        description="Distinctive tokens (award names, product names) that "
        "unblind the company and must be generalized by the Anonymizer.",
    )

    # Filled by Critic
    critic_report: CriticReport | None = None

    # Filled by CitationTracker
    citation_table: CitationTable | None = None

    # Output paths (set by renderers)
    pptx_path: Path | None = None
    citations_path: Path | None = None
    trace_path: Path | None = None
