"""Researcher: targeted Tavily queries + Flash summarization + planner_brief."""
from __future__ import annotations

import logging

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.tools import llm, web_search

log = logging.getLogger(__name__)

_SUMMARIZE_PROMPT = (
    "Summarize the following web page into 3-6 punchy bullet points "
    "useful for M&A investment analysis of '{company}'. Keep numbers verbatim. "
    "Max 400 words.\n\nTitle: {title}\nURL: {url}\n\nCONTENT:\n{content}"
)


def default_queries(company_name: str) -> list[str]:
    return [
        f"{company_name} product portfolio technical specifications and manufacturing capacity",
        f"{company_name} recent awards certifications and client case studies 2024 2025",
        f"{company_name} revenue breakdown by geography and segment annual report",
    ]


def build_planner_brief(docs: list[IngestedDoc], snippets: list[WebSnippet]) -> str:
    parts: list[str] = []
    if docs:
        parts.append("## PRIVATE DOCUMENTS")
        for d in docs:
            parts.append(f"### {d.filename} ({d.source_id})")
            parts.append(d.text.strip())
    if snippets:
        parts.append("\n## PUBLIC WEB SNIPPETS")
        for s in snippets:
            parts.append(f"### {s.url} ({s.source_id})")
            parts.append(s.summary.strip())
    return "\n".join(parts)


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    snippets: list[WebSnippet] = []
    for query in default_queries(state.company_name):
        hits = web_search.search(query, max_results=3)
        for hit in hits:
            if not hit.url or not hit.content:
                continue
            summary = _summarize_hit(state.company_name, hit)
            snippets.append(WebSnippet(
                source_id=f"web:tavily:{hit.url}",
                url=hit.url,
                summary=summary,
                query=query,
            ))

    brief = build_planner_brief(state.docs, snippets)

    web_research_empty = len(snippets) == 0
    if web_research_empty:
        log.warning(
            "Researcher: no Tavily hits across any query for %r; "
            "Planner brief will be doc-only.",
            state.company_name,
        )

    if trace_writer is not None:
        trace_writer.write_step("researcher", {
            "snippet_count": len(snippets),
            "brief_chars": len(brief),
            "web_research_empty": web_research_empty,
        })

    return {"web_snippets": snippets, "planner_brief": brief}


def _summarize_hit(company: str, hit) -> str:
    prompt = _SUMMARIZE_PROMPT.format(
        company=company, title=hit.title, url=hit.url,
        content=hit.content[:8000],
    )
    try:
        return llm.complete_text(MODEL_FAST, prompt, temperature=0.2)
    except Exception as e:  # noqa: BLE001
        log.error("Researcher summarize failed for %s: %s", hit.url, e)
        return hit.content[:500]
