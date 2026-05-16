"""Test fixture: monkeypatch the Gemini LLM client with canned responses.

Usage:
    from tests.fixtures.stub_llm import patch_llm

    def test_something(monkeypatch):
        patch_llm(monkeypatch, text_responses=["sector: SaaS"],
                  json_responses=[my_pydantic_obj])
        ...
"""
from __future__ import annotations

from collections import deque
from typing import Any

import kelp_teaser.tools.llm as llm_module


def patch_llm(
    monkeypatch,
    *,
    text_responses: list[str] | None = None,
    json_responses: list[Any] | None = None,
):
    """Replace complete_text and complete_json with deterministic stubs.

    Each call pops the next response. Raises IndexError if exhausted — make sure
    you pass enough responses for what the tested code path needs.
    """
    text_q: deque[str] = deque(text_responses or [])
    json_q: deque[Any] = deque(json_responses or [])

    def fake_complete_text(model, prompt, *, temperature=0.2, tracker=None):
        if not text_q:
            raise IndexError(f"stub_llm: text response queue exhausted "
                             f"(model={model}, prompt[:80]={prompt[:80]!r})")
        return text_q.popleft()

    def fake_complete_json(model, prompt, schema, *, temperature=0.2, tracker=None):
        if not json_q:
            raise IndexError(f"stub_llm: json response queue exhausted "
                             f"(model={model}, schema={schema.__name__})")
        obj = json_q.popleft()
        # If the test passed a dict, validate it through the schema for safety.
        if isinstance(obj, dict):
            return schema.model_validate(obj)
        return obj

    monkeypatch.setattr(llm_module, "complete_text", fake_complete_text)
    monkeypatch.setattr(llm_module, "complete_json", fake_complete_json)
