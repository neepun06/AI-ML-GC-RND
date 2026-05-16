"""Tavily search wrapper."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from tavily import TavilyClient

from kelp_teaser.config import TAVILY_API_KEY

log = logging.getLogger(__name__)


@dataclass
class TavilyHit:
    url: str
    title: str
    content: str


def search(query: str, max_results: int = 5) -> list[TavilyHit]:
    """Run a Tavily advanced search. Returns [] on any failure (logged)."""
    if not TAVILY_API_KEY:
        log.warning("TAVILY_API_KEY not set; web search disabled")
        return []
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        resp = client.search(query=query, search_depth="advanced", max_results=max_results)
        results = resp.get("results", []) if isinstance(resp, dict) else []
        return [
            TavilyHit(
                url=r.get("url", ""),
                title=r.get("title", ""),
                content=r.get("content", ""),
            )
            for r in results
        ]
    except Exception as e:  # noqa: BLE001
        log.error("Tavily search failed for %r: %s", query, e)
        return []
