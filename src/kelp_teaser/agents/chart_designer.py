"""ChartDesigner: Flash call that turns a chart-kind SectionPlan into a ChartSpec."""
from __future__ import annotations

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.schemas.plan import SectionPlan
from kelp_teaser.schemas.slide import ChartSpec
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt


def design_chart(section: SectionPlan, *, source_context: str) -> ChartSpec:
    if section.chart_spec is None:
        raise ValueError("design_chart requires SectionPlan.chart_spec to be set")
    prompt = load_prompt("chart_designer").render(
        chart_kind=section.chart_spec.chart_kind.value,
        heading=section.chart_spec.title or "",
        data_hooks=", ".join(section.data_hooks),
        source_context=source_context,
    )
    return llm.complete_json(MODEL_FAST, prompt, ChartSpec)
