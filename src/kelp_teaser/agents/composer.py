"""Composer: Pro call per slide. Writes the ComposedSlide for one SlidePlan.

Side calls: ChartDesigner for chart sections; ImageCurator for hero_image sections.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from kelp_teaser.agents import chart_designer, image_curator
from kelp_teaser.config import MODEL_SMART
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.schemas.plan import ComponentKind, SlidePlan
from kelp_teaser.schemas.slide import ComposedSection, ComposedSlide
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)


def build_source_context(docs: list[IngestedDoc],
                          snippets: list[WebSnippet]) -> str:
    parts: list[str] = []
    for d in docs:
        parts.append(f"### {d.source_id}\n{d.text.strip()}")
    for s in snippets:
        parts.append(f"### {s.source_id} (from {s.url})\n{s.summary.strip()}")
    return "\n\n".join(parts)


def compose_slide(
    *,
    slide_index: int,
    slide_plan: SlidePlan,
    codename: str,
    docs: list[IngestedDoc],
    web_snippets: list[WebSnippet],
    sector: str,
    out_dir: Path,
) -> ComposedSlide:
    source_context = build_source_context(docs, web_snippets)
    section_plans_json = json.dumps(
        [s.model_dump(mode="json") for s in slide_plan.sections],
        indent=2,
    )
    prompt = load_prompt("composer").render(
        slide_index=slide_index,
        slide_title=slide_plan.title,
        codename=codename,
        section_plans_json=section_plans_json,
        source_context=source_context,
    )
    composed: ComposedSlide = llm.complete_json(MODEL_SMART, prompt, ComposedSlide)

    composed = _attach_charts_and_images(
        composed=composed, slide_plan=slide_plan,
        source_context=source_context, sector=sector, out_dir=out_dir,
    )
    return composed


def _attach_charts_and_images(
    *,
    composed: ComposedSlide,
    slide_plan: SlidePlan,
    source_context: str,
    sector: str,
    out_dir: Path,
) -> ComposedSlide:
    """Pair each ComposedSection with its SectionPlan and run the side agents."""
    new_sections: list[ComposedSection] = []
    paired = list(zip(slide_plan.sections, composed.sections))
    for plan_sec, composed_sec in paired:
        if plan_sec.kind == ComponentKind.chart and composed_sec.chart is None:
            try:
                chart = chart_designer.design_chart(
                    plan_sec, source_context=source_context,
                )
                composed_sec = composed_sec.model_copy(update={"chart": chart})
            except Exception as e:  # noqa: BLE001
                log.error("ChartDesigner failed for slide %s: %s",
                          composed.index, e)
        elif plan_sec.kind == ComponentKind.hero_image and composed_sec.image is None:
            try:
                img = image_curator.curate_image(
                    plan_sec, sector=sector,
                    out_dir=out_dir / "images",
                )
                if img is not None:
                    composed_sec = composed_sec.model_copy(update={"image": img})
            except Exception as e:  # noqa: BLE001
                log.error("ImageCurator failed for slide %s: %s",
                          composed.index, e)
        new_sections.append(composed_sec)
    return composed.model_copy(update={"sections": new_sections})
