"""Critic: deterministic checks + a Flash judgment pass. Single pass, no loop."""
from __future__ import annotations

import json
import logging

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.critic import CriticIssue, CriticReport, CriticSeverity
from kelp_teaser.schemas.slide import ComposedSlide
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)

MAX_BULLET_WORDS = 20


def deterministic_checks(
    composed_slides: dict[int, ComposedSlide],
    *,
    valid_source_ids: set[str],
    real_name: str,
) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    real_lower = real_name.lower()

    for idx, slide in composed_slides.items():
        for section in slide.sections:
            for b in section.bullets:
                if b.source_id not in valid_source_ids:
                    issues.append(CriticIssue(
                        slide_index=idx, severity=CriticSeverity.blocking,
                        category="source_validity",
                        detail=f"bullet source_id {b.source_id!r} not found in inputs",
                    ))
                if len(b.text.split()) > MAX_BULLET_WORDS:
                    issues.append(CriticIssue(
                        slide_index=idx, severity=CriticSeverity.warning,
                        category="length_discipline",
                        detail=f"bullet >{MAX_BULLET_WORDS} words: {b.text[:60]!r}",
                    ))
                if real_lower in b.text.lower():
                    issues.append(CriticIssue(
                        slide_index=idx, severity=CriticSeverity.blocking,
                        category="anonymization_leak",
                        detail=f"bullet contains real name: {b.text[:60]!r}",
                    ))
            for m in section.metrics:
                if m.source_id not in valid_source_ids:
                    issues.append(CriticIssue(
                        slide_index=idx, severity=CriticSeverity.blocking,
                        category="source_validity",
                        detail=f"metric source_id {m.source_id!r} not found in inputs",
                    ))
                if real_lower in m.label.lower() or real_lower in m.subtext.lower():
                    issues.append(CriticIssue(
                        slide_index=idx, severity=CriticSeverity.blocking,
                        category="anonymization_leak",
                        detail=f"metric contains real name: {m.label!r}",
                    ))
            if section.chart is not None and section.chart.source_id not in valid_source_ids:
                issues.append(CriticIssue(
                    slide_index=idx, severity=CriticSeverity.warning,
                    category="source_validity",
                    detail=f"chart source_id {section.chart.source_id!r} not found",
                ))

    return issues


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    valid_source_ids = (
        {d.source_id for d in state.docs}
        | {s.source_id for s in state.web_snippets}
    )
    real_name = state.company_name
    codename = state.plan.codename if state.plan else "Project Blind"

    deterministic = deterministic_checks(
        state.composed_slides,
        valid_source_ids=valid_source_ids,
        real_name=real_name,
    )

    composed_json = json.dumps(
        {i: s.model_dump(mode="json") for i, s in state.composed_slides.items()},
        indent=2,
    )
    prompt = load_prompt("critic").render(
        codename=codename,
        real_name=real_name,
        sector=(state.sector.value if state.sector else "Other"),
        composed_slides_json=composed_json,
        source_ids_json=json.dumps(sorted(valid_source_ids)),
    )
    try:
        judgmental = llm.complete_json(MODEL_FAST, prompt, CriticReport).issues
    except Exception as e:  # noqa: BLE001
        log.error("Critic LLM judgment failed: %s", e)
        judgmental = [
            CriticIssue(
                slide_index=0,
                severity=CriticSeverity.warning,
                category="judgment_unavailable",
                detail=f"Critic LLM judgment call failed: {e}",
                suggested_fix="Inspect logs; re-run the Critic step if needed.",
            )
        ]

    report = CriticReport(issues=deterministic + judgmental)

    if trace_writer is not None:
        trace_writer.write_step("critic", {
            "deterministic_issues": len(deterministic),
            "judgmental_issues": len(judgmental),
            "blocking_count": sum(1 for i in report.issues
                                  if i.severity == CriticSeverity.blocking),
            "report": report.model_dump(),
        })

    return {"critic_report": report}
