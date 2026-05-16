from pathlib import Path

from kelp_teaser.agents.anonymizer import run as run_anonymizer
from kelp_teaser.graph.state import GraphState
from kelp_teaser.schemas.plan import (
    ChartKind, ChartSpecSkeleton, ComponentKind, DeckPlan, SectionPlan, SlidePlan,
)
from kelp_teaser.schemas.slide import (
    Bullet, ComposedSection, ComposedSlide, MetricTile,
)
from tests.fixtures.stub_llm import patch_llm


def _state_with_slides(slides):
    return GraphState(
        company_name="Ksolves", input_path=Path("."), run_id="r1",
        composed_slides={i: s for i, s in enumerate(slides)},
        plan=DeckPlan(codename="Project Halo", slides=[
            SlidePlan(title=f"Slide {i+1}", sections=[
                SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["x"]),
            ]) for i in range(3)
        ]),
    )


def test_anonymizer_replaces_real_name_in_bullets(monkeypatch):
    slide = ComposedSlide(index=0, title="Business Profile", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="Ksolves is a mid-cap player.", source_id="doc:x.md"),
            Bullet(text="600+ customers globally.", source_id="doc:x.md"),
        ]),
    ])
    # First bullet contains the name → 3 LLM calls (one per slide). Second bullet is clean → no call.
    patch_llm(monkeypatch, json_responses=[
        {"replacement": "Project Halo is a mid-cap player."},
        {"replacement": "Project Halo is a mid-cap player."},
        {"replacement": "Project Halo is a mid-cap player."},
    ])
    state = _state_with_slides([slide, slide.model_copy(update={"index": 1}),
                                slide.model_copy(update={"index": 2})])
    result = run_anonymizer(state)
    out_slide = result["composed_slides"][0]
    assert "Project Halo" in out_slide.sections[0].bullets[0].text
    assert "Ksolves" not in out_slide.sections[0].bullets[0].text
    # Second bullet untouched
    assert out_slide.sections[0].bullets[1].text == "600+ customers globally."
    # Log captures the substitution (3 total, one per slide)
    assert len(result["anonymization_log"]) == 3
    assert result["anonymization_log"][0].original.startswith("Ksolves")


def test_anonymizer_skips_clean_text_without_llm_call(monkeypatch):
    slide = ComposedSlide(index=0, title="Slide 1", sections=[
        ComposedSection(kind=ComponentKind.metric_tile, metrics=[
            MetricTile(value="₹450 Cr", label="Revenue FY24", source_id="doc:x.md"),
        ]),
    ])
    # No queue entries: if any LLM call happens, the test errors loudly.
    patch_llm(monkeypatch)
    state = _state_with_slides([slide, slide.model_copy(update={"index": 1}),
                                slide.model_copy(update={"index": 2})])
    result = run_anonymizer(state)
    # No substitutions recorded; slide unchanged
    assert result["anonymization_log"] == []
    assert result["composed_slides"][0].sections[0].metrics[0].value == "₹450 Cr"
