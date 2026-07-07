"""Anonymizer: Flash pass that scrubs identifying tokens from each bullet/metric.

Only calls Flash for items that *might* leak — anything containing the real company
name token (case-insensitive). Other text is passed through to save tokens.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.critic import Substitution
from kelp_teaser.schemas.slide import (
    Bullet,
    ComposedSection,
    ComposedSlide,
    MetricTile,
)
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)


class _Replacement(BaseModel):
    replacement: str


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    real_name = state.company_name
    codename = state.plan.codename if state.plan else "Project Blind"
    identifier_terms = state.identifier_terms
    log_entries: list[Substitution] = []
    new_slides: dict[int, ComposedSlide] = {}

    for idx, slide in state.composed_slides.items():
        new_sections: list[ComposedSection] = []
        for section in slide.sections:
            new_section = section.model_copy(deep=True)
            new_section.bullets = [
                _scrub_bullet(b, real_name, codename, idx, log_entries, identifier_terms)
                for b in section.bullets
            ]
            new_section.metrics = [
                _scrub_metric(m, real_name, codename, idx, log_entries, identifier_terms)
                for m in section.metrics
            ]
            new_sections.append(new_section)
        new_slides[idx] = slide.model_copy(update={"sections": new_sections})

    if trace_writer is not None:
        trace_writer.write_step("anonymizer", {
            "substitution_count": len(log_entries),
            "substitutions": [s.model_dump() for s in log_entries],
        })

    return {"composed_slides": new_slides, "anonymization_log": log_entries}


def _scrub_text(text: str, real_name: str, codename: str,
                identifier_terms: list[str] | None = None) -> str:
    terms = identifier_terms or []
    lower = text.lower()
    triggers = [real_name] + terms
    if not any(t and t.lower() in lower for t in triggers):
        return text
    prompt = load_prompt("anonymizer").render(
        real_name=real_name, codename=codename, original_text=text,
    )
    try:
        out = llm.complete_json(MODEL_FAST, prompt, _Replacement)
        return out.replacement or text
    except Exception as e:  # noqa: BLE001
        log.error("Anonymizer call failed: %s", e)
        # Fallback: case-insensitive literal swap of the company name.
        return _literal_swap(text, real_name, codename)


def _literal_swap(text: str, real_name: str, codename: str) -> str:
    # Case-insensitive replacement of whole/partial occurrences.
    out = []
    cursor = 0
    lower = text.lower()
    needle = real_name.lower()
    while cursor < len(text):
        hit = lower.find(needle, cursor)
        if hit == -1:
            out.append(text[cursor:])
            break
        out.append(text[cursor:hit])
        out.append(codename)
        cursor = hit + len(needle)
    return "".join(out)


def _scrub_bullet(b: Bullet, real_name: str, codename: str,
                  slide_idx: int, log_entries: list[Substitution],
                  identifier_terms: list[str]) -> Bullet:
    new_text = _scrub_text(b.text, real_name, codename, identifier_terms)
    if new_text != b.text:
        log_entries.append(Substitution(original=b.text, replacement=new_text,
                                        slide_index=slide_idx,
                                        reason="bullet leaked real name"))
        return b.model_copy(update={"text": new_text})
    return b


def _scrub_metric(m: MetricTile, real_name: str, codename: str,
                  slide_idx: int, log_entries: list[Substitution],
                  identifier_terms: list[str]) -> MetricTile:
    new_label = _scrub_text(m.label, real_name, codename, identifier_terms)
    new_subtext = _scrub_text(m.subtext, real_name, codename, identifier_terms) if m.subtext else ""
    if new_label != m.label or new_subtext != m.subtext:
        log_entries.append(Substitution(
            original=f"{m.label} | {m.subtext}",
            replacement=f"{new_label} | {new_subtext}",
            slide_index=slide_idx,
            reason="metric label/subtext leaked real name",
        ))
        return m.model_copy(update={"label": new_label, "subtext": new_subtext})
    return m
