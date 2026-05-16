"""Planner-output schemas: Sector, ChartKind, ComponentKind, SectionPlan, SlidePlan, DeckPlan."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Sector(str, Enum):
    Manufacturing = "Manufacturing"
    SpecialtyChemicals = "SpecialtyChemicals"
    D2C = "D2C"
    SaaS = "SaaS"
    Pharma = "Pharma"
    Logistics = "Logistics"
    FinancialServices = "FinancialServices"
    Consumer = "Consumer"
    Other = "Other"


class ChartKind(str, Enum):
    revenue_growth_bar = "revenue_growth_bar"
    revenue_growth_line = "revenue_growth_line"
    segment_mix_donut = "segment_mix_donut"
    margin_trend_line = "margin_trend_line"
    geo_split_stacked_bar = "geo_split_stacked_bar"
    channel_mix_donut = "channel_mix_donut"


class ComponentKind(str, Enum):
    metric_tile = "metric_tile"
    quadrant = "quadrant"
    chart = "chart"
    hero_image = "hero_image"
    bullet_list = "bullet_list"
    product_grid = "product_grid"
    kpi_strip = "kpi_strip"


class ChartSpecSkeleton(BaseModel):
    """Skeleton chart definition produced by the Planner. ChartDesigner fills in details."""

    chart_kind: ChartKind
    title: str = ""


class SectionPlan(BaseModel):
    kind: ComponentKind
    data_hooks: list[str] = Field(default_factory=list)
    chart_spec: ChartSpecSkeleton | None = None
    image_brief: str | None = None
    note: str = ""

    @model_validator(mode="after")
    def _validate_kind_specific_fields(self) -> "SectionPlan":
        if self.kind == ComponentKind.chart and self.chart_spec is None:
            raise ValueError("SectionPlan(kind=chart) requires chart_spec")
        if self.kind == ComponentKind.hero_image and not self.image_brief:
            raise ValueError("SectionPlan(kind=hero_image) requires image_brief")
        return self


class SlidePlan(BaseModel):
    title: str = Field(min_length=1)
    sections: list[SectionPlan] = Field(min_length=1, max_length=5)
    visual_priority: int = Field(default=1, ge=1, le=3)


class DeckPlan(BaseModel):
    codename: str = Field(min_length=1)
    slides: list[SlidePlan] = Field(min_length=3, max_length=3)
