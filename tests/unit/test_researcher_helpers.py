from pathlib import Path

from kelp_teaser.agents.researcher import (
    build_planner_brief,
    default_queries,
    run as run_researcher,
)
from kelp_teaser.graph.state import GraphState
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.tools.web_search import TavilyHit
from tests.fixtures.stub_llm import patch_llm


def _state(docs=None, snippets=None) -> GraphState:
    return GraphState(
        company_name="Ksolves",
        input_path=Path("."),
        run_id="r1",
        docs=docs or [IngestedDoc(source_id="doc:x.md", filename="x.md",
                                  text="Mid-cap IT services. Revenue ₹450 Cr.")],
        web_snippets=snippets or [],
    )


def test_default_queries_include_company_name():
    qs = default_queries("Acme Pharma")
    assert any("Acme Pharma" in q for q in qs)
    assert len(qs) >= 3


def test_build_planner_brief_contains_doc_text_and_snippet_summaries():
    docs = [IngestedDoc(source_id="doc:x.md", filename="x.md",
                        text="Revenue ₹450 Cr in FY24.")]
    snippets = [WebSnippet(source_id="web:tavily:https://acme.com",
                           url="https://acme.com", summary="Acme makes widgets.")]
    brief = build_planner_brief(docs, snippets)
    assert "₹450 Cr" in brief
    assert "Acme makes widgets" in brief
    assert len(brief) > 0


def test_researcher_works_when_tavily_returns_empty(monkeypatch):
    monkeypatch.setattr(
        "kelp_teaser.agents.researcher.web_search.search",
        lambda query, max_results=5: [],
    )
    patch_llm(monkeypatch)  # no LLM calls expected when no snippets
    state = _state()
    result = run_researcher(state)
    assert result["web_snippets"] == []
    assert "₹450 Cr" in result["planner_brief"]  # doc still in brief


def test_researcher_summarizes_each_hit_with_flash(monkeypatch):
    hits_by_query: dict[str, list[TavilyHit]] = {
        "Ksolves product portfolio technical specifications and manufacturing capacity":
            [TavilyHit(url="https://acme.com/products", title="Products",
                       content="Long page about products " * 50)],
    }
    def fake_search(query, max_results=5):
        return hits_by_query.get(query, [])
    monkeypatch.setattr("kelp_teaser.agents.researcher.web_search.search", fake_search)
    patch_llm(monkeypatch, text_responses=["Bullet: 600+ customers worldwide."])
    state = _state()
    result = run_researcher(state)
    assert len(result["web_snippets"]) == 1
    snippet = result["web_snippets"][0]
    assert snippet.source_id == "web:tavily:https://acme.com/products"
    assert "600+ customers" in snippet.summary
