"""Minimal fixture: three ComposedSlides with every section kind exercised at least once."""
from __future__ import annotations

from kelp_teaser.schemas.slide import (
    Bullet,
    ChartSeries,
    ChartSpec,
    ComposedSection,
    ComposedSlide,
    MetricTile,
)


def three_slides() -> list[ComposedSlide]:
    return [
        ComposedSlide(
            index=0,
            title="Business Profile",
            sections=[
                ComposedSection(
                    kind="bullet_list",
                    heading="Overview",
                    bullets=[
                        Bullet(text="Mid-cap technology services player",
                               source_id="doc:onepager.md"),
                        Bullet(text="Operations across India and the US",
                               source_id="web:tavily:https://example.com"),
                    ],
                ),
                ComposedSection(
                    kind="metric_tile",
                    metrics=[
                        MetricTile(value="600+", label="Customers",
                                   source_id="doc:onepager.md"),
                        MetricTile(value="22%", label="EBITDA Margin",
                                   source_id="doc:onepager.md"),
                        MetricTile(value="₹450 Cr", label="Revenue FY24",
                                   source_id="doc:onepager.md"),
                    ],
                ),
            ],
        ),
        ComposedSlide(
            index=1,
            title="Financial Performance",
            sections=[
                ComposedSection(
                    kind="chart",
                    heading="Revenue trajectory",
                    chart=ChartSpec(
                        chart_kind="revenue_growth_bar",
                        title="Revenue (₹ Cr)",
                        categories=["FY22", "FY23", "FY24"],
                        series=[ChartSeries(name="Revenue", values=[300, 380, 450])],
                        source_id="doc:onepager.md",
                    ),
                ),
                ComposedSection(
                    kind="bullet_list",
                    bullets=[Bullet(text="35% revenue from exports",
                                    source_id="doc:onepager.md")],
                ),
            ],
        ),
        ComposedSlide(
            index=2,
            title="Investment Thesis",
            sections=[
                ComposedSection(
                    kind="bullet_list",
                    bullets=[
                        Bullet(text="Strong recurring revenue mix",
                               source_id="doc:onepager.md"),
                        Bullet(text="Industry-leading retention",
                               source_id="doc:onepager.md"),
                    ],
                ),
            ],
        ),
    ]
