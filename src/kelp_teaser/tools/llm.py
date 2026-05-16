"""Gemini client wrapper with cost tracking and bounded retries.

LLM-touching code lives here. Agents call `complete_text` or `complete_json`.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel

from kelp_teaser.config import (
    GEMINI_API_KEY,
    LLM_MAX_ATTEMPTS,
    COST_SOFT_WARNING,
    COST_HARD_ABORT,
)

log = logging.getLogger(__name__)

# Indicative Gemini pricing (USD per 1M tokens). Adjust as Google updates rates.
# Source: https://ai.google.dev/pricing as of 2026-Q1. Numbers here are conservative.
_PRICING_USD_PER_1M: dict[str, tuple[float, float]] = {
    # model: (input_per_1m, output_per_1m)
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-2.5-pro": (1.25, 10.00),
}


def estimate_cost_usd(model: str, prompt_tokens: int, output_tokens: int) -> float:
    rates = _PRICING_USD_PER_1M.get(model)
    if rates is None:
        return 0.0
    in_rate, out_rate = rates
    return (prompt_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate


@dataclass
class GeminiCall:
    model: str
    prompt_tokens: int
    output_tokens: int
    elapsed_s: float = 0.0


@dataclass
class CostTracker:
    calls: list[GeminiCall] = field(default_factory=list)
    by_model: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def record(self, call: GeminiCall) -> None:
        cost = estimate_cost_usd(call.model, call.prompt_tokens, call.output_tokens)
        with self._lock:
            self.calls.append(call)
            self.by_model[call.model] += cost

    @property
    def total_calls(self) -> int:
        with self._lock:
            return len(self.calls)

    @property
    def total_cost_usd(self) -> float:
        with self._lock:
            return sum(self.by_model.values())


class CostExceeded(RuntimeError):
    pass


def check_cost_budget(tracker: CostTracker, *, soft_warning: float,
                      hard_abort: float) -> None:
    total = tracker.total_cost_usd
    if total > hard_abort:
        raise CostExceeded(
            f"Run cost ${total:.2f} exceeded hard abort threshold ${hard_abort:.2f}"
        )
    if total > soft_warning:
        log.warning("Run cost $%.2f exceeded soft warning $%.2f",
                    total, soft_warning)


# Module-level shared tracker, set by the CLI for the duration of a run.
CURRENT_TRACKER: CostTracker | None = None


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set; cannot call Gemini")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def complete_text(
    model: str,
    prompt: str,
    *,
    temperature: float = 0.2,
    tracker: CostTracker | None = None,
) -> str:
    """Single text completion with bounded retries. Raises on persistent failure."""
    if tracker is None:
        tracker = CURRENT_TRACKER
    last_exc: Exception | None = None
    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        try:
            start = time.monotonic()
            client = _get_client()
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(temperature=temperature),
            )
            elapsed = time.monotonic() - start
            text = resp.text or ""
            usage = getattr(resp, "usage_metadata", None)
            prompt_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
            output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
            if tracker is not None:
                tracker.record(GeminiCall(model, prompt_tokens, output_tokens, elapsed))
                check_cost_budget(
                    tracker,
                    soft_warning=COST_SOFT_WARNING,
                    hard_abort=COST_HARD_ABORT,
                )
            return text
        except Exception as e:  # noqa: BLE001 - Gemini SDK can raise many types
            last_exc = e
            log.warning("Gemini call failed (attempt %d/%d): %s", attempt, LLM_MAX_ATTEMPTS, e)
            time.sleep(min(2 ** attempt, 5))
    raise RuntimeError(f"Gemini call failed after {LLM_MAX_ATTEMPTS} attempts") from last_exc


def complete_json(
    model: str,
    prompt: str,
    schema: type[BaseModel],
    *,
    temperature: float = 0.2,
    tracker: CostTracker | None = None,
) -> BaseModel:
    """Completion that must return JSON matching the given Pydantic schema.

    On parse/validation failure, retries up to LLM_MAX_ATTEMPTS with a reminder appended.
    Raises on persistent failure.
    """
    if tracker is None:
        tracker = CURRENT_TRACKER
    schema_hint = (
        "\n\nRespond ONLY with valid JSON. No markdown fences. "
        "The JSON MUST validate against this schema:\n"
        f"{json.dumps(schema.model_json_schema(), indent=2)}"
    )
    augmented = prompt + schema_hint
    last_exc: Exception | None = None
    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        try:
            raw = complete_text(model, augmented, temperature=temperature, tracker=tracker)
            cleaned = _strip_code_fences(raw)
            data: Any = json.loads(cleaned)
            return schema.model_validate(data)
        except Exception as e:  # noqa: BLE001
            last_exc = e
            log.warning("complete_json failed (attempt %d/%d): %s",
                        attempt, LLM_MAX_ATTEMPTS, e)
            augmented = (
                prompt + schema_hint
                + "\n\nPrevious attempt failed validation; respond with strictly valid JSON."
            )
    raise RuntimeError(f"complete_json failed after {LLM_MAX_ATTEMPTS} attempts") from last_exc


def _strip_code_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.endswith("```"):
            s = s[: -3]
    return s.strip()
