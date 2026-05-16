"""Composed-slide schemas. These are what the Composer agent produces and renderers consume."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from kelp_teaser.schemas.facts import parse_source_id
from kelp_teaser.schemas.plan import ChartKind, ComponentKind


def _validate_source_id(v: str) -> str:
    parse_source_id(v)
    return v


class Bullet(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    source_id: str = Field(min_length=1)

    _v_source_id = field_validator("source_id")(_validate_source_id)


class MetricTile(BaseModel):
    value: str = Field(min_length=1)
    label: str = Field(min_length=1)
    subtext: str = ""
    source_id: str = Field(min_length=1)

    _v_source_id = field_validator("source_id")(_validate_source_id)


class ChartSeries(BaseModel):
    name: str = Field(min_length=1)
    values: list[float] = Field(min_length=1)


class ChartSpec(BaseModel):
    chart_kind: ChartKind
    title: str = ""
    categories: list[str] = Field(min_length=1)
    series: list[ChartSeries] = Field(min_length=1)
    y_axis_label: str = ""
    source_id: str = Field(min_length=1)

    _v_source_id = field_validator("source_id")(_validate_source_id)


class HeroImage(BaseModel):
    path: str = Field(min_length=1)
    alt_text: str = ""
    source_id: str = Field(min_length=1)  # image:pexels:<id>

    _v_source_id = field_validator("source_id")(_validate_source_id)


class ComposedSection(BaseModel):
    kind: ComponentKind
    heading: str = ""
    bullets: list[Bullet] = Field(default_factory=list)
    metrics: list[MetricTile] = Field(default_factory=list)
    chart: ChartSpec | None = None
    image: HeroImage | None = None

    def source_ids(self) -> set[str]:
        ids: set[str] = set()
        for b in self.bullets:
            ids.add(b.source_id)
        for m in self.metrics:
            ids.add(m.source_id)
        if self.chart is not None:
            ids.add(self.chart.source_id)
        if self.image is not None:
            ids.add(self.image.source_id)
        return ids


class ComposedSlide(BaseModel):
    index: int = Field(ge=0)
    title: str = Field(min_length=1)
    sections: list[ComposedSection] = Field(min_length=1)

    def all_source_ids(self) -> set[str]:
        ids: set[str] = set()
        for s in self.sections:
            ids |= s.source_ids()
        return ids
