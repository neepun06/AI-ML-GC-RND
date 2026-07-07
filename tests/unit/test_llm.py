import threading

import pytest
from pydantic import BaseModel, Field

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


class TestCostTrackerThreadSafety:
    def test_concurrent_record_preserves_all_calls(self):
        tracker = CostTracker()

        def worker():
            for _ in range(200):
                tracker.record(GeminiCall(model="gemini-2.5-flash",
                                          prompt_tokens=10, output_tokens=5))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert tracker.total_calls == 8 * 200

    def test_concurrent_record_preserves_cost_sum(self):
        tracker = CostTracker()

        def worker():
            for _ in range(200):
                tracker.record(GeminiCall(model="gemini-2.5-pro",
                                          prompt_tokens=1000, output_tokens=1000))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 8 * 200 = 1600 calls; per call: (1000/1M)*1.25 + (1000/1M)*10.0 = 0.01125 USD
        expected = 1600 * (1000 / 1_000_000 * 1.25 + 1000 / 1_000_000 * 10.0)
        assert abs(tracker.total_cost_usd - expected) < 1e-6


class _Widget(BaseModel):
    value: str = Field(min_length=1)


class TestCompleteJsonRetryFeedback:
    """complete_json must feed the specific validation errors back into the
    retry prompt so the model can self-correct, rather than repeating the
    same mistake against a generic 'try again' reminder."""

    def test_retry_prompt_includes_validation_error_and_recovers(self, monkeypatch):
        import kelp_teaser.tools.llm as llm_module

        prompts_seen: list[str] = []
        # First response is invalid (empty value violates min_length=1),
        # second response is valid.
        responses = iter(['{"value": ""}', '{"value": "ok"}'])

        def fake_complete_text(model, prompt, *, temperature=0.2, tracker=None):
            prompts_seen.append(prompt)
            return next(responses)

        monkeypatch.setattr(llm_module, "complete_text", fake_complete_text)

        result = llm_module.complete_json("gemini-2.5-flash", "base prompt", _Widget)

        # It recovered on the second attempt.
        assert isinstance(result, _Widget)
        assert result.value == "ok"
        # Two attempts were made.
        assert len(prompts_seen) == 2
        # The RETRY prompt carried the actual validation error detail, not
        # just a generic reminder. Pydantic's message mentions the field.
        assert "value" in prompts_seen[1]
        assert ("at least 1 character" in prompts_seen[1]
                or "validation error" in prompts_seen[1].lower())


class TestCostGuardrail:
    def test_check_cost_budget_under_warning_passes(self):
        from kelp_teaser.tools.llm import (
            CostExceeded,
            check_cost_budget,
        )
        tracker = CostTracker()
        tracker.record(GeminiCall(model="gemini-2.5-flash",
                                  prompt_tokens=10, output_tokens=5))
        check_cost_budget(tracker, soft_warning=2.00, hard_abort=5.00)

    def test_check_cost_budget_over_abort_raises(self):
        from kelp_teaser.tools.llm import (
            CostExceeded,
            check_cost_budget,
        )
        tracker = CostTracker()
        # Force cost > $5 by recording many expensive Pro calls.
        for _ in range(1000):
            tracker.record(GeminiCall(model="gemini-2.5-pro",
                                      prompt_tokens=10_000, output_tokens=10_000))
        with pytest.raises(CostExceeded):
            check_cost_budget(tracker, soft_warning=2.00, hard_abort=5.00)
