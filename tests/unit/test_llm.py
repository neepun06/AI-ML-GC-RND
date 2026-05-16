import pytest

from kelp_teaser.tools.llm import (
    CostTracker,
    GeminiCall,
    estimate_cost_usd,
)


class TestCostTracker:
    def test_records_calls_and_sums_cost(self):
        tracker = CostTracker()
        tracker.record(GeminiCall(model="gemini-2.5-flash", prompt_tokens=1000,
                                  output_tokens=500))
        tracker.record(GeminiCall(model="gemini-2.5-pro", prompt_tokens=2000,
                                  output_tokens=800))
        assert tracker.total_calls == 2
        assert tracker.total_cost_usd > 0
        assert tracker.by_model["gemini-2.5-flash"] >= 0
        assert tracker.by_model["gemini-2.5-pro"] >= 0


class TestEstimateCost:
    def test_flash_cheaper_than_pro_at_same_tokens(self):
        flash = estimate_cost_usd("gemini-2.5-flash", 1000, 1000)
        pro = estimate_cost_usd("gemini-2.5-pro", 1000, 1000)
        assert pro > flash

    def test_unknown_model_returns_zero(self):
        assert estimate_cost_usd("nonexistent-model", 1000, 1000) == 0.0
