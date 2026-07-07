from pathlib import Path

from kelp_teaser.agents.critic import (
    deterministic_checks,
    run as run_critic,
)
from kelp_teaser.graph.state import GraphState
from kelp_teaser.schemas.critic import CriticReport
from kelp_teaser.schemas.facts import IngestedDoc
from kelp_teaser.schemas.plan import (
    ChartKind, ChartSpecSkeleton, ComponentKind, DeckPlan, Sector,
    SectionPlan, SlidePlan,
)
from kelp_teaser.schemas.slide import (
    Bullet, ComposedSection, ComposedSlide, MetricTile,
)
from tests.fixtures.stub_llm import patch_llm


def _state(slides):
    return GraphState(
        company_name="Ksolves", input_path=Path("."), run_id="r1",
        docs=[IngestedDoc(source_id="doc:x.md", filename="x.md", text="t")],
        composed_slides={i: s for i, s in enumerate(slides)},
        sector=Sector.SaaS,
        plan=DeckPlan(codename="Project Halo", slides=[
            SlidePlan(title=f"Slide {i+1}", sections=[
                SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["x"]),
            ]) for i in range(3)
        ]),
    )


def test_deterministic_checks_flags_long_bullet():
    long_text = "word " * 25
    slide = ComposedSlide(index=0, title="t", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text=long_text.strip(), source_id="doc:x.md"),
        ]),
    ])
    issues = deterministic_checks({0: slide}, valid_source_ids={"doc:x.md"},
                                  real_name="Ksolves")
    assert any(i.category == "length_discipline" for i in issues)


def test_deterministic_checks_flags_missing_source_id():
    # Use a *valid* source_id at the model layer, but not present in the
    # valid_source_ids set the Critic was given.
    slide = ComposedSlide(index=0, title="t", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="something", source_id="doc:NOT_INGESTED.pdf"),
        ]),
    ])
    issues = deterministic_checks({0: slide}, valid_source_ids={"doc:x.md"},
                                  real_name="Ksolves")
    assert any(i.category == "source_validity" for i in issues)


def test_deterministic_checks_flags_real_name_leak():
    slide = ComposedSlide(index=0, title="t", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="Ksolves is great.", source_id="doc:x.md"),
        ]),
    ])
    issues = deterministic_checks({0: slide}, valid_source_ids={"doc:x.md"},
                                  real_name="Ksolves")
    assert any(i.category == "anonymization_leak" for i in issues)


def test_critic_merges_llm_and_deterministic(monkeypatch):
    slide = ComposedSlide(index=0, title="t", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="clean", source_id="doc:x.md"),
        ]),
    ])
    state = _state([slide, slide.model_copy(update={"index": 1}),
                    slide.model_copy(update={"index": 2})])
    patch_llm(monkeypatch, json_responses=[CriticReport(issues=[])])
    result = run_critic(state)
    assert result["critic_report"].issues == []


def test_critic_appends_judgment_unavailable_when_llm_raises(monkeypatch):
    """When the Flash judgment call fails, the report must contain a
    synthetic 'judgment_unavailable' warning rather than silently returning
    only deterministic issues (which read as 'all clear')."""
    import kelp_teaser.tools.llm as llm_module

    def boom(model, prompt, schema, *, temperature=0.2, tracker=None):
        raise RuntimeError("simulated Gemini timeout")

    monkeypatch.setattr(llm_module, "complete_json", boom)

    slide = ComposedSlide(index=0, title="t", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="clean", source_id="doc:x.md"),
        ]),
    ])
    state = _state([slide, slide.model_copy(update={"index": 1}),
                    slide.model_copy(update={"index": 2})])

    result = run_critic(state)
    report = result["critic_report"]
    judgment_issues = [i for i in report.issues
                       if i.category == "judgment_unavailable"]
    assert len(judgment_issues) == 1
    assert judgment_issues[0].severity.value == "warning"
    assert "simulated Gemini timeout" in judgment_issues[0].detail
    assert report.has_blocking() is False
