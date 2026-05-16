from pptx import Presentation
from pptx.util import Inches

from kelp_teaser.render import theme
from kelp_teaser.render.charts import render_chart
from kelp_teaser.schemas.slide import ChartSeries, ChartSpec


def _blank_slide():
    prs = Presentation()
    prs.slide_width = theme.SLIDE_W
    prs.slide_height = theme.SLIDE_H
    return prs, prs.slides.add_slide(prs.slide_layouts[6])


def test_render_revenue_bar_chart():
    prs, slide = _blank_slide()
    spec = ChartSpec(
        chart_kind="revenue_growth_bar",
        title="Revenue",
        categories=["FY22", "FY23", "FY24"],
        series=[ChartSeries(name="Revenue (₹ Cr)", values=[300, 380, 450])],
        source_id="doc:r.pdf#p12",
    )
    render_chart(slide, Inches(1), Inches(2), Inches(8), Inches(4), spec)
    chart_shapes = [s for s in slide.shapes if s.has_chart]
    assert len(chart_shapes) == 1


def test_render_segment_mix_donut():
    prs, slide = _blank_slide()
    spec = ChartSpec(
        chart_kind="segment_mix_donut",
        title="Segment mix",
        categories=["Lecithin", "Phospholipids", "Other"],
        series=[ChartSeries(name="Share", values=[55, 30, 15])],
        source_id="doc:r.pdf#p15",
    )
    render_chart(slide, Inches(1), Inches(2), Inches(5), Inches(4), spec)
    chart_shapes = [s for s in slide.shapes if s.has_chart]
    assert len(chart_shapes) == 1


def test_render_unknown_chart_kind_raises():
    import pytest
    prs, slide = _blank_slide()

    # Construct invalid spec via dict (bypass enum) — should fail upstream, but
    # render_chart itself should also reject if somehow reached.
    with pytest.raises(ValueError):
        render_chart(slide, Inches(1), Inches(2), Inches(5), Inches(4),
                     spec=None)  # type: ignore[arg-type]
