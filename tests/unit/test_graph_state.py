from pathlib import Path

import pytest
from pydantic import ValidationError

from kelp_teaser.graph.state import GraphState
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.schemas.plan import Sector


def test_graph_state_requires_company_input_run_id():
    with pytest.raises(ValidationError):
        GraphState(company_name="", input_path=Path("."), run_id="r1")
    with pytest.raises(ValidationError):
        GraphState(company_name="Acme", input_path=Path("."), run_id="")


def test_graph_state_has_empty_defaults():
    s = GraphState(company_name="Acme", input_path=Path("."), run_id="r1")
    assert s.docs == []
    assert s.web_snippets == []
    assert s.planner_brief == ""
    assert s.sector is None
    assert s.composed_slides == {}
    assert s.anonymization_log == []
    assert s.critic_report is None
    assert s.citation_table is None


def test_graph_state_accepts_partial_updates():
    s = GraphState(company_name="Acme", input_path=Path("."), run_id="r1",
                   docs=[IngestedDoc(source_id="doc:x.md", filename="x.md", text="t")])
    s2 = s.model_copy(update={"sector": Sector.SaaS})
    assert s2.sector == Sector.SaaS
    assert s2.docs[0].filename == "x.md"


def test_graph_state_composed_slides_keyed_by_int():
    from kelp_teaser.schemas.slide import Bullet, ComposedSection, ComposedSlide

    slide = ComposedSlide(
        index=0, title="t",
        sections=[ComposedSection(
            kind="bullet_list",
            bullets=[Bullet(text="x", source_id="doc:r.md")],
        )],
    )
    s = GraphState(company_name="Acme", input_path=Path("."), run_id="r1",
                   composed_slides={0: slide})
    assert 0 in s.composed_slides


def test_graph_state_web_snippets_validated():
    s = GraphState(company_name="Acme", input_path=Path("."), run_id="r1",
                   web_snippets=[WebSnippet(source_id="web:tavily:https://x.com",
                                            url="https://x.com")])
    assert len(s.web_snippets) == 1
