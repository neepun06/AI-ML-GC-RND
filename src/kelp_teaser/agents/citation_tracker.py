"""CitationTracker: pure aggregation; produces the structured citation table."""
from __future__ import annotations

from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.citations import CitationRow, CitationTable
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet


def _verbatim_quote_for(source_id: str, docs: list[IngestedDoc],
                         snippets: list[WebSnippet], claim: str) -> str:
    """Best-effort: pull a short verbatim from the source matching the claim."""
    for d in docs:
        if d.source_id == source_id:
            return _excerpt_around(d.text, claim)
    for s in snippets:
        if s.source_id == source_id:
            return _excerpt_around(s.summary, claim)
    return ""


def _excerpt_around(text: str, claim: str, window: int = 140) -> str:
    if not text:
        return ""
    needle = claim.split()[0] if claim else ""
    idx = text.lower().find(needle.lower()) if needle else -1
    if idx == -1:
        return text[:window]
    start = max(0, idx - window // 4)
    return text[start: start + window].strip()


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    rows: list[CitationRow] = []
    for idx, slide in sorted(state.composed_slides.items()):
        for section in slide.sections:
            for b in section.bullets:
                rows.append(CitationRow(
                    slide_index=idx, claim=b.text, source_id=b.source_id,
                    verbatim_quote=_verbatim_quote_for(b.source_id, state.docs,
                                                       state.web_snippets, b.text),
                    confidence="High",
                ))
            for m in section.metrics:
                claim = f"{m.label}: {m.value}" + (f" ({m.subtext})" if m.subtext else "")
                rows.append(CitationRow(
                    slide_index=idx, claim=claim, source_id=m.source_id,
                    verbatim_quote=_verbatim_quote_for(m.source_id, state.docs,
                                                       state.web_snippets, m.value),
                    confidence="High",
                ))
            if section.chart is not None:
                rows.append(CitationRow(
                    slide_index=idx,
                    claim=f"Chart: {section.chart.title or section.chart.chart_kind.value}",
                    source_id=section.chart.source_id,
                    verbatim_quote=_verbatim_quote_for(section.chart.source_id,
                                                       state.docs, state.web_snippets,
                                                       section.chart.title or ""),
                    confidence="Medium",
                ))
            if section.image is not None:
                rows.append(CitationRow(
                    slide_index=idx,
                    claim=f"Image: {section.image.alt_text or 'stock photo'}",
                    source_id=section.image.source_id,
                    verbatim_quote="Pexels stock photo (CC0 license)",
                    confidence="High",
                ))

    table = CitationTable(rows=rows)
    if trace_writer is not None:
        trace_writer.write_step("citation_tracker", {"row_count": len(rows)})
    return {"citation_table": table}
