"""Native python-pptx chart renderer for the 6 supported chart kinds."""
from __future__ import annotations

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.util import Emu

from kelp_teaser.schemas.plan import ChartKind
from kelp_teaser.schemas.slide import ChartSpec

_KIND_TO_XL: dict[ChartKind, int] = {
    ChartKind.revenue_growth_bar: XL_CHART_TYPE.COLUMN_CLUSTERED,
    ChartKind.revenue_growth_line: XL_CHART_TYPE.LINE,
    ChartKind.segment_mix_donut: XL_CHART_TYPE.DOUGHNUT,
    ChartKind.margin_trend_line: XL_CHART_TYPE.LINE,
    ChartKind.geo_split_stacked_bar: XL_CHART_TYPE.COLUMN_STACKED,
    ChartKind.channel_mix_donut: XL_CHART_TYPE.DOUGHNUT,
}


def render_chart(slide, x: Emu, y: Emu, w: Emu, h: Emu, spec: ChartSpec) -> None:
    """Render a native PowerPoint chart onto `slide` per `spec`."""
    if spec is None or not isinstance(spec, ChartSpec):
        raise ValueError("render_chart requires a ChartSpec instance")

    xl_kind = _KIND_TO_XL.get(spec.chart_kind)
    if xl_kind is None:
        raise ValueError(f"unsupported chart kind: {spec.chart_kind!r}")

    data = CategoryChartData()
    data.categories = spec.categories
    for series in spec.series:
        data.add_series(series.name, series.values)

    chart = slide.shapes.add_chart(xl_kind, x, y, w, h, data).chart
    chart.has_title = bool(spec.title)
    if spec.title:
        chart.chart_title.text_frame.text = spec.title

    if spec.chart_kind in (ChartKind.segment_mix_donut, ChartKind.channel_mix_donut):
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.RIGHT
        chart.legend.include_in_layout = False
