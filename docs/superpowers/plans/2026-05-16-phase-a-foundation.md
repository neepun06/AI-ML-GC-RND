# Phase A: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the v2 folder structure, schemas, prompts scaffold, tool wrappers, renderers, and Kelp theme — every non-agentic piece needed before the LangGraph wiring begins. After Phase A, no user-facing pipeline runs yet, but every later phase depends on this foundation being correct.

**Architecture:** Pure-function modules organized under `src/kelp_teaser/` with clear single responsibilities. Pydantic for all data contracts. Prompts loaded from Jinja2-templated Markdown files. The v1 code keeps running alongside v2 until Phase B replaces it.

**Tech Stack:** Python 3.11+, Pydantic v2, python-pptx, python-docx, Jinja2, pytest, LlamaParse, Tavily, Pexels, Gemini API (google-generativeai). LangGraph and agent wiring come in Phase B.

**Reference spec:** [docs/superpowers/specs/2026-05-16-agentic-teaser-pipeline-design.md](../specs/2026-05-16-agentic-teaser-pipeline-design.md)

---

## File Structure (created in this phase)

```
src/kelp_teaser/
├── __init__.py
├── config.py
├── schemas/
│   ├── __init__.py
│   ├── facts.py
│   ├── plan.py
│   ├── slide.py
│   ├── critic.py
│   └── citations.py
├── tools/
│   ├── __init__.py
│   ├── llm.py             # Gemini client (Flash + Pro), cost tracking
│   ├── pdf_parser.py      # LlamaParse wrapper
│   ├── excel_parser.py    # pandas
│   ├── web_search.py      # Tavily
│   ├── image_search.py    # Pexels
│   └── prompt_loader.py   # Jinja2 .md loader
└── render/
    ├── __init__.py
    ├── theme.py           # Kelp branding constants
    ├── slide_components.py
    ├── charts.py
    ├── deck.py
    └── citations_doc.py

prompts/                   # empty placeholder files; filled in Phase B
├── sector_classifier.md
├── planner.md
├── composer.md
├── chart_designer.md
├── image_curator.md
├── anonymizer.md
└── critic.md

data/
├── inputs/                # data packs moved here
└── outputs/               # per-run folders go here

tests/
├── __init__.py
├── unit/
│   ├── __init__.py
│   ├── test_schemas.py
│   ├── test_prompt_loader.py
│   ├── test_theme.py
│   ├── test_charts.py
│   ├── test_deck_render.py
│   └── test_citations_doc.py
└── fixtures/
    ├── __init__.py
    └── ksolves_minimal.py  # minimal ComposedSlide fixtures for render tests

pyproject.toml             # replaces requirements.txt
.env.example
.gitignore                 # updated
```

---

## Task 1: Project metadata, dependencies, gitignore

**Files:**
- Create: `pyproject.toml`
- Modify: `.gitignore`
- Create: `.env.example`

- [ ] **Step 1: Write `pyproject.toml`**

Create `pyproject.toml` with:

```toml
[project]
name = "kelp-teaser"
version = "0.2.0"
description = "Agentic M&A teaser generation pipeline"
requires-python = ">=3.11"
dependencies = [
    "python-pptx>=0.6.23",
    "python-docx>=1.1.0",
    "google-generativeai>=0.8.0",
    "python-dotenv>=1.0.1",
    "requests>=2.32.0",
    "llama-parse>=0.5.0",
    "tavily-python>=0.5.0",
    "pandas>=2.2.0",
    "openpyxl>=3.1.2",
    "Pillow>=10.4.0",
    "lxml>=5.3.0",
    "pydantic>=2.9.0",
    "jinja2>=3.1.4",
    "langgraph>=0.2.50",
    "langchain-core>=0.3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=5.0.0",
]

[project.scripts]
kelp-teaser = "kelp_teaser.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Update `.gitignore`**

Append to `.gitignore`:

```
# v2 outputs
data/outputs/

# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
build/
dist/

# IDE
.vscode/
.idea/

# Env
.env
```

- [ ] **Step 3: Write `.env.example`**

Create `.env.example` with:

```
GEMINI_API_KEY=your_gemini_key_here
TAVILY_API_KEY=your_tavily_key_here
LLAMA_CLOUD_API_KEY=your_llama_key_here
PEXELS_API_KEY=your_pexels_key_here
```

- [ ] **Step 4: Install dev dependencies**

Run: `pip install -e ".[dev]"`
Expected: installs successfully; `pytest --version` works.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore .env.example
git commit -m "chore: add pyproject.toml and v2 .gitignore/.env.example"
```

---

## Task 2: Folder scaffolding and config module

**Files:**
- Create: `src/kelp_teaser/__init__.py`
- Create: `src/kelp_teaser/config.py`
- Create: `src/kelp_teaser/schemas/__init__.py`
- Create: `src/kelp_teaser/tools/__init__.py`
- Create: `src/kelp_teaser/render/__init__.py`
- Create: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/fixtures/__init__.py`
- Create: `data/inputs/.gitkeep`, `data/outputs/.gitkeep`
- Create: `prompts/.gitkeep`

- [ ] **Step 1: Create empty package init files**

Run:
```bash
mkdir -p src/kelp_teaser/schemas src/kelp_teaser/tools src/kelp_teaser/render
mkdir -p tests/unit tests/fixtures
mkdir -p data/inputs data/outputs prompts
touch src/kelp_teaser/__init__.py
touch src/kelp_teaser/schemas/__init__.py
touch src/kelp_teaser/tools/__init__.py
touch src/kelp_teaser/render/__init__.py
touch tests/__init__.py tests/unit/__init__.py tests/fixtures/__init__.py
touch data/inputs/.gitkeep data/outputs/.gitkeep prompts/.gitkeep
```

- [ ] **Step 2: Write `src/kelp_teaser/config.py`**

```python
"""Centralized configuration: paths, model IDs, branding, cost guardrails."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "prompts"
DATA_INPUTS_DIR = REPO_ROOT / "data" / "inputs"
DATA_OUTPUTS_DIR = REPO_ROOT / "data" / "outputs"

# API keys (None-tolerant; tools check and raise where required)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Model IDs
MODEL_FAST = "gemini-2.5-flash"
MODEL_SMART = "gemini-2.5-pro"

# Cost guardrails (USD)
COST_SOFT_WARNING = 2.00
COST_HARD_ABORT = 5.00

# Retry policy
LLM_MAX_ATTEMPTS = 2

# Parallel composer fan-out cap
MAX_PARALLEL_SLIDES = 3
```

- [ ] **Step 3: Write the failing test**

Create `tests/unit/test_config.py`:

```python
from pathlib import Path
from kelp_teaser import config


def test_repo_root_resolves_to_directory_containing_pyproject():
    assert (config.REPO_ROOT / "pyproject.toml").exists()


def test_default_paths_are_under_repo_root():
    assert config.PROMPTS_DIR == config.REPO_ROOT / "prompts"
    assert config.DATA_INPUTS_DIR == config.REPO_ROOT / "data" / "inputs"
    assert config.DATA_OUTPUTS_DIR == config.REPO_ROOT / "data" / "outputs"


def test_model_ids_are_defined():
    assert config.MODEL_FAST == "gemini-2.5-flash"
    assert config.MODEL_SMART == "gemini-2.5-pro"


def test_cost_guardrails_are_sane():
    assert 0 < config.COST_SOFT_WARNING < config.COST_HARD_ABORT
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/ tests/ data/ prompts/
git commit -m "feat: scaffold v2 package layout and config module"
```

---

## Task 3: `SourceRef` and `Fact` schemas (citation integrity foundation)

**Files:**
- Create: `src/kelp_teaser/schemas/facts.py`
- Create: `tests/unit/test_schemas.py`

- [ ] **Step 1: Write failing test for `SourceRef`**

Create `tests/unit/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from kelp_teaser.schemas.facts import (
    SourceRef,
    Fact,
    IngestedDoc,
    WebSnippet,
    parse_source_id,
)


class TestSourceRef:
    def test_doc_source_id_roundtrip(self):
        ref = SourceRef(source_id="doc:annual_report.pdf#p12")
        assert ref.kind == "doc"
        assert ref.locator == "annual_report.pdf#p12"

    def test_web_source_id_roundtrip(self):
        ref = SourceRef(source_id="web:tavily:https://example.com/about")
        assert ref.kind == "web"
        assert ref.locator == "tavily:https://example.com/about"

    def test_image_source_id_roundtrip(self):
        ref = SourceRef(source_id="image:pexels:12345")
        assert ref.kind == "image"
        assert ref.locator == "pexels:12345"

    def test_invalid_source_id_rejected(self):
        with pytest.raises(ValidationError):
            SourceRef(source_id="not_a_valid_id")

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValidationError):
            SourceRef(source_id="phone:404:nothing")


class TestFact:
    def test_fact_requires_non_empty_source_id(self):
        with pytest.raises(ValidationError):
            Fact(value="some claim", source_id="", verbatim_quote="quote")

    def test_fact_requires_value(self):
        with pytest.raises(ValidationError):
            Fact(value="", source_id="doc:x.pdf#p1", verbatim_quote="quote")

    def test_fact_valid(self):
        f = Fact(
            value="Revenue ₹450 Cr in FY24",
            source_id="doc:annual_report.pdf#p12",
            verbatim_quote="Total revenue stood at ₹450 crore",
        )
        assert f.value == "Revenue ₹450 Cr in FY24"
        assert f.source_id == "doc:annual_report.pdf#p12"


class TestIngestedDoc:
    def test_ingested_doc_minimal(self):
        d = IngestedDoc(
            source_id="doc:report.pdf",
            filename="report.pdf",
            text="Lorem ipsum",
        )
        assert d.source_id == "doc:report.pdf"


class TestWebSnippet:
    def test_web_snippet_minimal(self):
        s = WebSnippet(
            source_id="web:tavily:https://x.com",
            url="https://x.com",
            summary="Bullet summary",
        )
        assert s.source_id == "web:tavily:https://x.com"


def test_parse_source_id_helper():
    assert parse_source_id("doc:a.pdf#p1") == ("doc", "a.pdf#p1")
    assert parse_source_id("web:tavily:https://x.com") == ("web", "tavily:https://x.com")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_schemas.py -v`
Expected: collection error or ImportError on `kelp_teaser.schemas.facts`.

- [ ] **Step 3: Implement `schemas/facts.py`**

Create `src/kelp_teaser/schemas/facts.py`:

```python
"""Source-tracked fact schemas. Every claim on a slide is a Fact with a source_id."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SourceKind = Literal["doc", "web", "image"]
ALLOWED_KINDS: tuple[str, ...] = ("doc", "web", "image")


def parse_source_id(source_id: str) -> tuple[str, str]:
    """Split `kind:locator` into (kind, locator). Raises ValueError on malformed input."""
    if ":" not in source_id:
        raise ValueError(f"source_id missing ':' separator: {source_id!r}")
    kind, _, locator = source_id.partition(":")
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"unknown source kind {kind!r}; allowed: {ALLOWED_KINDS}")
    if not locator:
        raise ValueError(f"source_id has empty locator: {source_id!r}")
    return kind, locator


class SourceRef(BaseModel):
    """A reference to a single source document, web page, or image."""

    source_id: str = Field(min_length=1)

    @property
    def kind(self) -> str:
        return parse_source_id(self.source_id)[0]

    @property
    def locator(self) -> str:
        return parse_source_id(self.source_id)[1]

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        parse_source_id(v)  # raises ValueError on bad input
        return v


class Fact(BaseModel):
    """A textual claim plus the source it was extracted from."""

    value: str = Field(min_length=1, description="The claim as it will appear on the slide.")
    source_id: str = Field(min_length=1)
    verbatim_quote: str = Field(
        default="",
        description="Exact substring from the source supporting this claim.",
    )

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        parse_source_id(v)
        return v


class IngestedDoc(BaseModel):
    """A parsed private document from the data pack."""

    source_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    text: str = ""
    page_anchors: dict[str, str] = Field(
        default_factory=dict,
        description="Optional map of page/section labels to text chunks.",
    )

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        kind, _ = parse_source_id(v)
        if kind != "doc":
            raise ValueError(f"IngestedDoc source_id must start with 'doc:'; got {v!r}")
        return v


class WebSnippet(BaseModel):
    """A summarized search hit from the public web."""

    source_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    summary: str = ""
    query: str = ""

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        kind, _ = parse_source_id(v)
        if kind != "web":
            raise ValueError(f"WebSnippet source_id must start with 'web:'; got {v!r}")
        return v
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_schemas.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/schemas/facts.py tests/unit/test_schemas.py
git commit -m "feat(schemas): add SourceRef, Fact, IngestedDoc, WebSnippet"
```

---

## Task 4: Plan schemas (`Sector`, `ChartKind`, `ComponentKind`, `SectionPlan`, `SlidePlan`, `DeckPlan`)

**Files:**
- Create: `src/kelp_teaser/schemas/plan.py`
- Modify: `tests/unit/test_schemas.py`

- [ ] **Step 1: Append failing tests to `tests/unit/test_schemas.py`**

Append to `tests/unit/test_schemas.py`:

```python
from kelp_teaser.schemas.plan import (
    Sector,
    ChartKind,
    ComponentKind,
    SectionPlan,
    SlidePlan,
    DeckPlan,
)


class TestSector:
    def test_known_sectors_exist(self):
        for name in [
            "Manufacturing",
            "SpecialtyChemicals",
            "D2C",
            "SaaS",
            "Pharma",
            "Logistics",
            "FinancialServices",
            "Consumer",
            "Other",
        ]:
            assert Sector(name) == getattr(Sector, name)


class TestSectionPlan:
    def test_chart_section_requires_chart_kind(self):
        with pytest.raises(ValidationError):
            SectionPlan(kind=ComponentKind.chart, data_hooks=["revenue"])

    def test_image_section_requires_image_brief(self):
        with pytest.raises(ValidationError):
            SectionPlan(kind=ComponentKind.hero_image, data_hooks=[])

    def test_metric_section_no_extra_fields_required(self):
        s = SectionPlan(kind=ComponentKind.metric_tile, data_hooks=["revenue_fy24"])
        assert s.kind == ComponentKind.metric_tile


class TestDeckPlan:
    def test_deck_must_have_exactly_three_slides(self):
        with pytest.raises(ValidationError):
            DeckPlan(
                codename="Project Halo",
                slides=[
                    SlidePlan(title="Slide 1", sections=[
                        SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["x"])
                    ])
                ],
            )

    def test_deck_codename_required(self):
        with pytest.raises(ValidationError):
            DeckPlan(codename="", slides=_three_minimal_slides())

    def test_deck_valid(self):
        plan = DeckPlan(codename="Project Halo", slides=_three_minimal_slides())
        assert plan.codename == "Project Halo"
        assert len(plan.slides) == 3


def _three_minimal_slides() -> list[SlidePlan]:
    return [
        SlidePlan(
            title=f"Slide {i + 1}",
            sections=[SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["x"])],
        )
        for i in range(3)
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_schemas.py -v`
Expected: import errors / failures on the new classes.

- [ ] **Step 3: Implement `schemas/plan.py`**

Create `src/kelp_teaser/schemas/plan.py`:

```python
"""Planner-output schemas: Sector, ChartKind, ComponentKind, SectionPlan, SlidePlan, DeckPlan."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Sector(str, Enum):
    Manufacturing = "Manufacturing"
    SpecialtyChemicals = "SpecialtyChemicals"
    D2C = "D2C"
    SaaS = "SaaS"
    Pharma = "Pharma"
    Logistics = "Logistics"
    FinancialServices = "FinancialServices"
    Consumer = "Consumer"
    Other = "Other"


class ChartKind(str, Enum):
    revenue_growth_bar = "revenue_growth_bar"
    revenue_growth_line = "revenue_growth_line"
    segment_mix_donut = "segment_mix_donut"
    margin_trend_line = "margin_trend_line"
    geo_split_stacked_bar = "geo_split_stacked_bar"
    channel_mix_donut = "channel_mix_donut"


class ComponentKind(str, Enum):
    metric_tile = "metric_tile"
    quadrant = "quadrant"
    chart = "chart"
    hero_image = "hero_image"
    bullet_list = "bullet_list"
    product_grid = "product_grid"
    kpi_strip = "kpi_strip"


class ChartSpecSkeleton(BaseModel):
    """Skeleton chart definition produced by the Planner. ChartDesigner fills in details."""

    chart_kind: ChartKind
    title: str = ""


class SectionPlan(BaseModel):
    kind: ComponentKind
    data_hooks: list[str] = Field(default_factory=list)
    chart_spec: ChartSpecSkeleton | None = None
    image_brief: str | None = None
    note: str = ""

    @model_validator(mode="after")
    def _validate_kind_specific_fields(self) -> "SectionPlan":
        if self.kind == ComponentKind.chart and self.chart_spec is None:
            raise ValueError("SectionPlan(kind=chart) requires chart_spec")
        if self.kind == ComponentKind.hero_image and not self.image_brief:
            raise ValueError("SectionPlan(kind=hero_image) requires image_brief")
        return self


class SlidePlan(BaseModel):
    title: str = Field(min_length=1)
    sections: list[SectionPlan] = Field(min_length=1, max_length=5)
    visual_priority: int = Field(default=1, ge=1, le=3)


class DeckPlan(BaseModel):
    codename: str = Field(min_length=1)
    slides: list[SlidePlan] = Field(min_length=3, max_length=3)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_schemas.py -v`
Expected: all schema tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/schemas/plan.py tests/unit/test_schemas.py
git commit -m "feat(schemas): add Sector, ChartKind, ComponentKind, SectionPlan, SlidePlan, DeckPlan"
```

---

## Task 5: Composed-slide schemas (`Bullet`, `MetricTile`, `ChartSpec`, `ComposedSection`, `ComposedSlide`)

**Files:**
- Create: `src/kelp_teaser/schemas/slide.py`
- Modify: `tests/unit/test_schemas.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/test_schemas.py`:

```python
from kelp_teaser.schemas.slide import (
    Bullet,
    MetricTile,
    ChartSpec,
    ChartSeries,
    ComposedSection,
    ComposedSlide,
)


class TestComposedSection:
    def test_section_with_bullets_requires_each_bullet_to_have_source(self):
        with pytest.raises(ValidationError):
            ComposedSection(
                kind="bullet_list",
                bullets=[Bullet(text="some claim", source_id="")],
            )

    def test_section_with_metrics_requires_each_metric_to_have_source(self):
        with pytest.raises(ValidationError):
            ComposedSection(
                kind="metric_tile",
                metrics=[MetricTile(value="₹450 Cr", label="Revenue", source_id="")],
            )

    def test_valid_bullet_section_round_trips(self):
        section = ComposedSection(
            kind="bullet_list",
            bullets=[
                Bullet(text="5 facilities across western India", source_id="doc:report.pdf#p4"),
                Bullet(text="600+ active customers", source_id="web:tavily:https://x.com"),
            ],
        )
        assert len(section.bullets) == 2


class TestComposedSlide:
    def test_composed_slide_minimal(self):
        slide = ComposedSlide(
            index=0,
            title="Business Profile",
            sections=[
                ComposedSection(
                    kind="bullet_list",
                    bullets=[Bullet(text="A claim", source_id="doc:r.pdf#p1")],
                )
            ],
        )
        assert slide.index == 0

    def test_composed_slide_collects_all_source_ids(self):
        slide = ComposedSlide(
            index=1,
            title="Financials",
            sections=[
                ComposedSection(
                    kind="metric_tile",
                    metrics=[
                        MetricTile(value="₹450 Cr", label="Revenue FY24",
                                   source_id="doc:r.pdf#p12"),
                        MetricTile(value="22%", label="EBITDA Margin",
                                   source_id="doc:r.pdf#p14"),
                    ],
                ),
                ComposedSection(
                    kind="bullet_list",
                    bullets=[Bullet(text="X", source_id="web:tavily:https://x.com")],
                ),
            ],
        )
        ids = slide.all_source_ids()
        assert ids == {"doc:r.pdf#p12", "doc:r.pdf#p14", "web:tavily:https://x.com"}


class TestChartSpec:
    def test_chart_spec_requires_series(self):
        with pytest.raises(ValidationError):
            ChartSpec(
                chart_kind="revenue_growth_bar",
                title="Revenue",
                categories=["FY22", "FY23"],
                series=[],
                source_id="doc:r.pdf#p12",
            )

    def test_chart_spec_valid(self):
        c = ChartSpec(
            chart_kind="revenue_growth_bar",
            title="Revenue",
            categories=["FY22", "FY23", "FY24"],
            series=[ChartSeries(name="Revenue (₹ Cr)", values=[300, 380, 450])],
            source_id="doc:r.pdf#p12",
        )
        assert c.series[0].values == [300, 380, 450]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_schemas.py -v`
Expected: import errors on the new symbols.

- [ ] **Step 3: Implement `schemas/slide.py`**

Create `src/kelp_teaser/schemas/slide.py`:

```python
"""Composed-slide schemas. These are what the Composer agent produces and renderers consume."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from kelp_teaser.schemas.facts import parse_source_id
from kelp_teaser.schemas.plan import ChartKind, ComponentKind


def _validate_source_id(v: str) -> str:
    parse_source_id(v)
    return v


class Bullet(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    source_id: str = Field(min_length=1)

    _v_source_id = field_validator("source_id")(_validate_source_id)


class MetricTile(BaseModel):
    value: str = Field(min_length=1)
    label: str = Field(min_length=1)
    subtext: str = ""
    source_id: str = Field(min_length=1)

    _v_source_id = field_validator("source_id")(_validate_source_id)


class ChartSeries(BaseModel):
    name: str = Field(min_length=1)
    values: list[float] = Field(min_length=1)


class ChartSpec(BaseModel):
    chart_kind: ChartKind
    title: str = ""
    categories: list[str] = Field(min_length=1)
    series: list[ChartSeries] = Field(min_length=1)
    y_axis_label: str = ""
    source_id: str = Field(min_length=1)

    _v_source_id = field_validator("source_id")(_validate_source_id)


class HeroImage(BaseModel):
    path: str = Field(min_length=1)
    alt_text: str = ""
    source_id: str = Field(min_length=1)  # image:pexels:<id>

    _v_source_id = field_validator("source_id")(_validate_source_id)


class ComposedSection(BaseModel):
    kind: ComponentKind
    heading: str = ""
    bullets: list[Bullet] = Field(default_factory=list)
    metrics: list[MetricTile] = Field(default_factory=list)
    chart: ChartSpec | None = None
    image: HeroImage | None = None

    def source_ids(self) -> set[str]:
        ids: set[str] = set()
        for b in self.bullets:
            ids.add(b.source_id)
        for m in self.metrics:
            ids.add(m.source_id)
        if self.chart is not None:
            ids.add(self.chart.source_id)
        if self.image is not None:
            ids.add(self.image.source_id)
        return ids


class ComposedSlide(BaseModel):
    index: int = Field(ge=0)
    title: str = Field(min_length=1)
    sections: list[ComposedSection] = Field(min_length=1)

    def all_source_ids(self) -> set[str]:
        ids: set[str] = set()
        for s in self.sections:
            ids |= s.source_ids()
        return ids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_schemas.py -v`
Expected: all schema tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/schemas/slide.py tests/unit/test_schemas.py
git commit -m "feat(schemas): add Bullet, MetricTile, ChartSpec, ComposedSection, ComposedSlide"
```

---

## Task 6: Critic and citations schemas

**Files:**
- Create: `src/kelp_teaser/schemas/critic.py`
- Create: `src/kelp_teaser/schemas/citations.py`
- Modify: `tests/unit/test_schemas.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/test_schemas.py`:

```python
from kelp_teaser.schemas.critic import (
    CriticIssue,
    CriticReport,
    CriticSeverity,
    Substitution,
)
from kelp_teaser.schemas.citations import CitationRow, CitationTable


class TestCriticReport:
    def test_critic_issue_severity_enum(self):
        i = CriticIssue(
            slide_index=1,
            severity=CriticSeverity.blocking,
            category="source_validity",
            detail="Claim missing source",
        )
        assert i.severity == CriticSeverity.blocking

    def test_critic_report_groups_by_slide(self):
        report = CriticReport(
            issues=[
                CriticIssue(slide_index=0, severity=CriticSeverity.warning,
                            category="length", detail="bullet too long"),
                CriticIssue(slide_index=2, severity=CriticSeverity.blocking,
                            category="anonymization", detail="leaked name"),
            ],
        )
        assert report.issues_for_slide(0)[0].category == "length"
        assert report.has_blocking() is True


class TestSubstitution:
    def test_substitution_minimal(self):
        s = Substitution(original="Centum Electronics", replacement="Project Halo", slide_index=0)
        assert s.original == "Centum Electronics"


class TestCitationTable:
    def test_citation_row_minimal(self):
        row = CitationRow(
            slide_index=0,
            claim="Revenue ₹450 Cr",
            source_id="doc:r.pdf#p12",
            verbatim_quote="Total revenue stood at ₹450 crore",
            confidence="High",
        )
        assert row.slide_index == 0

    def test_citation_table_roundtrip(self):
        t = CitationTable(rows=[
            CitationRow(slide_index=0, claim="X", source_id="doc:r.pdf#p1",
                        verbatim_quote="X", confidence="High"),
        ])
        assert len(t.rows) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_schemas.py -v`
Expected: import errors.

- [ ] **Step 3: Implement `schemas/critic.py`**

Create `src/kelp_teaser/schemas/critic.py`:

```python
"""Critic and anonymization schemas."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CriticSeverity(str, Enum):
    info = "info"
    warning = "warning"
    blocking = "blocking"


class CriticIssue(BaseModel):
    slide_index: int = Field(ge=0)
    severity: CriticSeverity
    category: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    suggested_fix: str = ""


class CriticReport(BaseModel):
    issues: list[CriticIssue] = Field(default_factory=list)

    def issues_for_slide(self, idx: int) -> list[CriticIssue]:
        return [i for i in self.issues if i.slide_index == idx]

    def has_blocking(self) -> bool:
        return any(i.severity == CriticSeverity.blocking for i in self.issues)


class Substitution(BaseModel):
    original: str = Field(min_length=1)
    replacement: str = Field(min_length=1)
    slide_index: int = Field(ge=0)
    reason: str = ""
```

- [ ] **Step 4: Implement `schemas/citations.py`**

Create `src/kelp_teaser/schemas/citations.py`:

```python
"""Citation-doc schemas."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from kelp_teaser.schemas.facts import parse_source_id


ConfidenceLevel = Literal["High", "Medium", "Low"]


class CitationRow(BaseModel):
    slide_index: int = Field(ge=0)
    claim: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    verbatim_quote: str = ""
    confidence: ConfidenceLevel = "Medium"

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        parse_source_id(v)
        return v


class CitationTable(BaseModel):
    rows: list[CitationRow] = Field(default_factory=list)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_schemas.py -v`
Expected: all schema tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/schemas/critic.py src/kelp_teaser/schemas/citations.py tests/unit/test_schemas.py
git commit -m "feat(schemas): add CriticIssue, CriticReport, Substitution, CitationRow, CitationTable"
```

---

## Task 7: Prompt loader (Jinja2-templated Markdown)

**Files:**
- Create: `src/kelp_teaser/tools/prompt_loader.py`
- Create: `tests/unit/test_prompt_loader.py`
- Create: 7 empty placeholder files under `prompts/`

- [ ] **Step 1: Create empty prompt placeholder files**

Run:
```bash
for f in sector_classifier planner composer chart_designer image_curator anonymizer critic; do
  echo "# $f prompt (TODO Phase B)" > prompts/$f.md
done
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/test_prompt_loader.py`:

```python
import pytest

from kelp_teaser.tools.prompt_loader import Prompt, load_prompt, PromptNotFoundError


def test_load_known_prompt_returns_prompt_instance():
    p = load_prompt("sector_classifier")
    assert isinstance(p, Prompt)


def test_load_unknown_prompt_raises():
    with pytest.raises(PromptNotFoundError):
        load_prompt("does_not_exist")


def test_prompt_render_substitutes_variables(tmp_path, monkeypatch):
    prompt_file = tmp_path / "demo.md"
    prompt_file.write_text("Hello {{ name }}, sector is {{ sector }}.")
    monkeypatch.setattr("kelp_teaser.tools.prompt_loader.PROMPTS_DIR", tmp_path)
    p = load_prompt("demo")
    out = p.render(name="Halo", sector="Pharma")
    assert out == "Hello Halo, sector is Pharma."


def test_prompt_render_raises_on_missing_variable(tmp_path, monkeypatch):
    prompt_file = tmp_path / "demo.md"
    prompt_file.write_text("Hello {{ name }}")
    monkeypatch.setattr("kelp_teaser.tools.prompt_loader.PROMPTS_DIR", tmp_path)
    p = load_prompt("demo")
    with pytest.raises(Exception):  # jinja2.UndefinedError
        p.render()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_prompt_loader.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `tools/prompt_loader.py`**

Create `src/kelp_teaser/tools/prompt_loader.py`:

```python
"""Load Jinja2-templated Markdown prompts from the prompts/ directory."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

from kelp_teaser.config import PROMPTS_DIR as _DEFAULT_PROMPTS_DIR

PROMPTS_DIR: Path = _DEFAULT_PROMPTS_DIR


class PromptNotFoundError(FileNotFoundError):
    pass


class Prompt:
    def __init__(self, name: str, template_text: str) -> None:
        self.name = name
        env = Environment(undefined=StrictUndefined, autoescape=False)
        self._template = env.from_string(template_text)

    def render(self, **kwargs: object) -> str:
        return self._template.render(**kwargs)


def load_prompt(name: str) -> Prompt:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise PromptNotFoundError(f"prompt not found: {path}")
    return Prompt(name=name, template_text=path.read_text(encoding="utf-8"))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_prompt_loader.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add prompts/ src/kelp_teaser/tools/prompt_loader.py tests/unit/test_prompt_loader.py
git commit -m "feat(tools): prompt loader with Jinja2 + strict undefined"
```

---

## Task 8: LLM client wrapper (Gemini Flash + Pro, retry, cost tracking)

**Files:**
- Create: `src/kelp_teaser/tools/llm.py`
- Create: `tests/unit/test_llm.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_llm.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_llm.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `tools/llm.py`**

Create `src/kelp_teaser/tools/llm.py`:

```python
"""Gemini client wrapper with cost tracking and bounded retries.

LLM-touching code lives here. Agents call `complete_text` or `complete_json`.
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import google.generativeai as genai
from pydantic import BaseModel

from kelp_teaser.config import GEMINI_API_KEY, LLM_MAX_ATTEMPTS

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

    def record(self, call: GeminiCall) -> None:
        cost = estimate_cost_usd(call.model, call.prompt_tokens, call.output_tokens)
        self.calls.append(call)
        self.by_model[call.model] += cost

    @property
    def total_calls(self) -> int:
        return len(self.calls)

    @property
    def total_cost_usd(self) -> float:
        return sum(self.by_model.values())


def _configure_gemini() -> None:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set; cannot call Gemini")
    genai.configure(api_key=GEMINI_API_KEY)


def complete_text(
    model: str,
    prompt: str,
    *,
    temperature: float = 0.2,
    tracker: CostTracker | None = None,
) -> str:
    """Single text completion with bounded retries. Raises on persistent failure."""
    _configure_gemini()
    last_exc: Exception | None = None
    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        try:
            start = time.monotonic()
            m = genai.GenerativeModel(model)
            resp = m.generate_content(
                prompt,
                generation_config={"temperature": temperature},
            )
            elapsed = time.monotonic() - start
            text = resp.text or ""
            usage = getattr(resp, "usage_metadata", None)
            prompt_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
            output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
            if tracker is not None:
                tracker.record(GeminiCall(model, prompt_tokens, output_tokens, elapsed))
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
    _configure_gemini()
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_llm.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/tools/llm.py tests/unit/test_llm.py
git commit -m "feat(tools): Gemini LLM client with retry, JSON-schema mode, cost tracking"
```

---

## Task 9: PDF, Excel, web, and image tool wrappers

**Files:**
- Create: `src/kelp_teaser/tools/pdf_parser.py`
- Create: `src/kelp_teaser/tools/excel_parser.py`
- Create: `src/kelp_teaser/tools/web_search.py`
- Create: `src/kelp_teaser/tools/image_search.py`
- Create: `tests/unit/test_tools.py`

- [ ] **Step 1: Write failing test for the pure-Python parts**

Create `tests/unit/test_tools.py`:

```python
import io

import pandas as pd
import pytest

from kelp_teaser.tools.excel_parser import flatten_workbook
from kelp_teaser.tools.image_search import build_pexels_query_url


def test_flatten_workbook_handles_single_sheet():
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="Financials")
    buf.seek(0)
    text = flatten_workbook(buf)
    assert "Sheet: Financials" in text
    assert "A" in text and "B" in text


def test_build_pexels_query_url_includes_query():
    url = build_pexels_query_url("chemical reactor", orientation="landscape", per_page=5)
    assert "query=chemical+reactor" in url or "query=chemical%20reactor" in url
    assert "orientation=landscape" in url
    assert "per_page=5" in url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_tools.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `tools/pdf_parser.py`**

Create `src/kelp_teaser/tools/pdf_parser.py`:

```python
"""LlamaParse wrapper for PDF ingestion."""
from __future__ import annotations

import logging
from pathlib import Path

from llama_parse import LlamaParse

from kelp_teaser.config import LLAMA_CLOUD_API_KEY

log = logging.getLogger(__name__)


def parse_pdf(file_path: Path) -> str:
    """Parse a PDF file into markdown text. Returns empty string on failure (logged)."""
    if not LLAMA_CLOUD_API_KEY:
        log.warning("LLAMA_CLOUD_API_KEY not set; skipping PDF: %s", file_path)
        return ""
    try:
        parser = LlamaParse(
            api_key=LLAMA_CLOUD_API_KEY,
            result_type="markdown",
            verbose=False,
        )
        docs = parser.load_data(str(file_path))
        if not docs:
            return ""
        return docs[0].text or ""
    except Exception as e:  # noqa: BLE001
        log.error("PDF parse failed for %s: %s", file_path, e)
        return ""
```

- [ ] **Step 4: Implement `tools/excel_parser.py`**

Create `src/kelp_teaser/tools/excel_parser.py`:

```python
"""Excel workbook flattener."""
from __future__ import annotations

from typing import IO, Union

import pandas as pd


def flatten_workbook(source: Union[str, IO[bytes]]) -> str:
    """Read every sheet and return a single text dump suitable for LLM ingestion."""
    sheets: dict[str, pd.DataFrame] = pd.read_excel(source, sheet_name=None)
    parts: list[str] = []
    for name, df in sheets.items():
        parts.append(f"[Sheet: {name}]")
        parts.append(df.to_string())
        parts.append("")
    return "\n".join(parts)
```

- [ ] **Step 5: Implement `tools/web_search.py`**

Create `src/kelp_teaser/tools/web_search.py`:

```python
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
```

- [ ] **Step 6: Implement `tools/image_search.py`**

Create `src/kelp_teaser/tools/image_search.py`:

```python
"""Pexels image search wrapper."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import requests

from kelp_teaser.config import PEXELS_API_KEY

log = logging.getLogger(__name__)


@dataclass
class PexelsCandidate:
    photo_id: int
    src_large: str
    photographer: str
    photographer_url: str
    alt: str


def build_pexels_query_url(query: str, *, orientation: str = "landscape", per_page: int = 5) -> str:
    params = {"query": query, "orientation": orientation, "per_page": per_page}
    return f"https://api.pexels.com/v1/search?{urlencode(params)}"


def search_pexels(query: str, *, per_page: int = 5) -> list[PexelsCandidate]:
    if not PEXELS_API_KEY:
        log.warning("PEXELS_API_KEY not set; image search disabled")
        return []
    try:
        url = build_pexels_query_url(query, per_page=per_page)
        resp = requests.get(url, headers={"Authorization": PEXELS_API_KEY}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [
            PexelsCandidate(
                photo_id=p.get("id", 0),
                src_large=p.get("src", {}).get("large", ""),
                photographer=p.get("photographer", ""),
                photographer_url=p.get("photographer_url", ""),
                alt=p.get("alt", ""),
            )
            for p in data.get("photos", [])
        ]
    except Exception as e:  # noqa: BLE001
        log.error("Pexels search failed for %r: %s", query, e)
        return []


def download_image(url: str, dest: Path) -> bool:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Image download failed (%s -> %s): %s", url, dest, e)
        return False
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/unit/test_tools.py -v`
Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add src/kelp_teaser/tools/pdf_parser.py src/kelp_teaser/tools/excel_parser.py \
        src/kelp_teaser/tools/web_search.py src/kelp_teaser/tools/image_search.py \
        tests/unit/test_tools.py
git commit -m "feat(tools): PDF/Excel/Tavily/Pexels wrappers with fail-soft logging"
```

---

## Task 10: Render theme (Kelp branding constants, ported from v1)

**Files:**
- Create: `src/kelp_teaser/render/theme.py`
- Create: `tests/unit/test_theme.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_theme.py`:

```python
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from kelp_teaser.render import theme


def test_palette_has_required_keys():
    for k in ("primary", "accent", "accent_gradient_end", "cyan", "bg_slide",
              "white", "text_dark", "text_muted", "border_light"):
        assert k in theme.PALETTE
        assert isinstance(theme.PALETTE[k], RGBColor)


def test_slide_dimensions_widescreen():
    assert theme.SLIDE_W == Inches(13.333)
    assert theme.SLIDE_H == Inches(7.5)


def test_footer_text_matches_brand_guidelines():
    assert theme.FOOTER_TEXT == "Strictly Private & Confidential – Prepared by Kelp M&A Team"
    assert theme.FOOTER_FONT_SIZE == Pt(9)


def test_heading_font_is_arial_bold():
    assert theme.HEADING_FONT == "Arial"
    assert theme.BODY_FONT == "Arial"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_theme.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `render/theme.py`**

Create `src/kelp_teaser/render/theme.py`:

```python
"""Kelp branding constants — colors, fonts, dimensions, footer text.

Source of truth for everything visual. Renderers MUST NOT define their own
colors or fonts; they pull from here.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

PALETTE: dict[str, RGBColor] = {
    "primary": RGBColor(40, 0, 80),            # Dark Indigo / Violet
    "accent": RGBColor(255, 100, 80),          # Pink → Orange gradient start
    "accent_gradient_end": RGBColor(255, 160, 60),  # Pink → Orange gradient end
    "cyan": RGBColor(50, 180, 230),            # Cyan Blue (icons)
    "bg_slide": RGBColor(255, 255, 255),       # Clean white content background
    "white": RGBColor(255, 255, 255),
    "text_dark": RGBColor(45, 45, 55),
    "text_muted": RGBColor(100, 100, 110),
    "border_light": RGBColor(220, 220, 230),
}

# Slide dimensions (widescreen 16:9)
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

# Page margins and layout
MARGIN = Inches(0.5)
GUTTER = Inches(0.3)
CONTENT_W = SLIDE_W - (MARGIN * 2)
COL2_W = (CONTENT_W - GUTTER) / 2
COL3_W = (CONTENT_W - GUTTER * 2) / 3

# Typography
HEADING_FONT = "Arial"
BODY_FONT = "Arial"
HEADING_SIZE = Pt(24)
SUBHEADING_SIZE = Pt(14)
BODY_SIZE = Pt(11)
CAPTION_SIZE = Pt(9)

# Footer
FOOTER_TEXT = "Strictly Private & Confidential – Prepared by Kelp M&A Team"
FOOTER_FONT_SIZE = Pt(9)

# Header
HEADER_HEIGHT = Inches(1.3)
LOGO_PLACEHOLDER_TEXT = "Kelp"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_theme.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/render/theme.py tests/unit/test_theme.py
git commit -m "feat(render): Kelp branding theme constants"
```

---

## Task 11: Slide-component primitives (header, footer, container, metric tile, bullets, product grid)

**Files:**
- Create: `src/kelp_teaser/render/slide_components.py`
- Create: `tests/unit/test_slide_components.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_slide_components.py`:

```python
from pptx import Presentation
from pptx.util import Inches

from kelp_teaser.render import theme
from kelp_teaser.render.slide_components import (
    add_header,
    add_footer,
    draw_container,
    draw_metric_tile,
    draw_bullet_list,
)
from kelp_teaser.schemas.slide import Bullet, MetricTile


def _blank_slide():
    prs = Presentation()
    prs.slide_width = theme.SLIDE_W
    prs.slide_height = theme.SLIDE_H
    return prs, prs.slides.add_slide(prs.slide_layouts[6])


def test_add_header_adds_shapes():
    prs, slide = _blank_slide()
    before = len(slide.shapes)
    add_header(slide, codename="Project Halo", subtitle="Manufacturing | Teaser")
    assert len(slide.shapes) > before


def test_add_footer_text_matches_brand():
    prs, slide = _blank_slide()
    add_footer(slide)
    texts = [s.text_frame.text for s in slide.shapes if s.has_text_frame]
    assert any(theme.FOOTER_TEXT in t for t in texts)


def test_draw_container_returns_shape():
    prs, slide = _blank_slide()
    shape = draw_container(slide, Inches(0.5), Inches(1.5), Inches(6), Inches(3), title="Profile")
    assert shape is not None


def test_draw_metric_tile_renders_value_and_label():
    prs, slide = _blank_slide()
    tile = MetricTile(value="₹450 Cr", label="Revenue FY24", source_id="doc:r.pdf#p1")
    draw_metric_tile(slide, Inches(0.5), Inches(1.5), Inches(2.0), Inches(1.8), tile)
    texts = [s.text_frame.text for s in slide.shapes if s.has_text_frame]
    assert any("₹450 Cr" in t for t in texts)
    assert any("REVENUE FY24" in t.upper() for t in texts)


def test_draw_bullet_list_renders_each_bullet():
    prs, slide = _blank_slide()
    bullets = [
        Bullet(text="5 facilities in western India", source_id="doc:r.pdf#p1"),
        Bullet(text="600+ active customers", source_id="web:tavily:https://x.com"),
    ]
    draw_bullet_list(slide, Inches(0.5), Inches(1.5), Inches(6), Inches(4), bullets)
    texts = [s.text_frame.text for s in slide.shapes if s.has_text_frame]
    joined = "\n".join(texts)
    assert "5 facilities" in joined
    assert "600+ active" in joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_slide_components.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `render/slide_components.py`**

Create `src/kelp_teaser/render/slide_components.py`:

```python
"""Reusable slide components: header, footer, container, metric tile, bullets.

All visual primitives the deck renderer composes from. No business logic here —
just shapes and text styled per `theme.py`.
"""
from __future__ import annotations

from typing import Iterable

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

from kelp_teaser.render import theme
from kelp_teaser.schemas.slide import Bullet, MetricTile


def _style_run(run, *, font=None, size=None, bold=False, color=None):
    run.font.name = font or theme.BODY_FONT
    if size is not None:
        run.font.size = size
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def add_header(slide, *, codename: str, subtitle: str = "") -> None:
    """Draw the Dark Indigo top band with codename + subtitle + Kelp logo placeholder."""
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
                                theme.SLIDE_W, theme.HEADER_HEIGHT)
    bg.fill.solid()
    bg.fill.fore_color.rgb = theme.PALETTE["primary"]
    bg.line.fill.background()

    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(0.6))
    p = title_box.text_frame.paragraphs[0]
    p.text = codename
    _style_run(p.runs[0], font=theme.HEADING_FONT, size=theme.HEADING_SIZE,
               bold=True, color=theme.PALETTE["white"])

    if subtitle:
        sub_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.75), Inches(9), Inches(0.3))
        p2 = sub_box.text_frame.paragraphs[0]
        p2.text = subtitle
        _style_run(p2.runs[0], font=theme.BODY_FONT, size=theme.SUBHEADING_SIZE,
                   color=theme.PALETTE["white"])

    # Kelp logo placeholder (text, top-right). Real logo asset wired later if desired.
    logo_box = slide.shapes.add_textbox(Inches(11.6), Inches(0.35), Inches(1.4), Inches(0.6))
    p3 = logo_box.text_frame.paragraphs[0]
    p3.text = theme.LOGO_PLACEHOLDER_TEXT
    p3.alignment = PP_ALIGN.RIGHT
    _style_run(p3.runs[0], font=theme.HEADING_FONT, size=theme.HEADING_SIZE,
               bold=True, color=theme.PALETTE["white"])


def add_footer(slide) -> None:
    """Brand-mandated centered footer at 9pt."""
    box = slide.shapes.add_textbox(Inches(0), Inches(7.15), Inches(13.3), Inches(0.3))
    p = box.text_frame.paragraphs[0]
    p.text = theme.FOOTER_TEXT
    p.alignment = PP_ALIGN.CENTER
    _style_run(p.runs[0], size=theme.FOOTER_FONT_SIZE, color=theme.PALETTE["text_muted"])


def draw_container(slide, x: Emu, y: Emu, w: Emu, h: Emu, *, title: str = ""):
    """White rounded card with a subtle shadow. Returns the card shape."""
    shadow = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                    x + Pt(3), y + Pt(3), w, h)
    shadow.fill.solid()
    shadow.fill.fore_color.rgb = theme.PALETTE["border_light"]
    shadow.line.fill.background()

    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    box.fill.solid()
    box.fill.fore_color.rgb = theme.PALETTE["white"]
    box.line.color.rgb = theme.PALETTE["border_light"]

    if title:
        tb = slide.shapes.add_textbox(x + Pt(10), y + Pt(8), w - Pt(20), Inches(0.4))
        p = tb.text_frame.paragraphs[0]
        p.text = title.upper()
        _style_run(p.runs[0], font=theme.HEADING_FONT, size=Pt(11),
                   bold=True, color=theme.PALETTE["primary"])

    return box


def draw_metric_tile(slide, x: Emu, y: Emu, w: Emu, h: Emu, tile: MetricTile) -> None:
    """A big-number metric card. Value on top, label below, optional subtext."""
    draw_container(slide, x, y, w, h)

    val_box = slide.shapes.add_textbox(x, y + Pt(5), w, Inches(0.7))
    p = val_box.text_frame.paragraphs[0]
    p.text = tile.value
    p.alignment = PP_ALIGN.CENTER
    _style_run(p.runs[0], font=theme.HEADING_FONT, size=Pt(28),
               bold=True, color=theme.PALETTE["accent"])

    lbl_box = slide.shapes.add_textbox(x, y + Pt(50), w, Inches(0.3))
    p = lbl_box.text_frame.paragraphs[0]
    p.text = tile.label.upper()
    p.alignment = PP_ALIGN.CENTER
    _style_run(p.runs[0], font=theme.HEADING_FONT, size=Pt(9),
               bold=True, color=theme.PALETTE["primary"])

    if tile.subtext:
        sub_box = slide.shapes.add_textbox(x, y + Pt(70), w, Inches(0.4))
        p = sub_box.text_frame.paragraphs[0]
        p.text = tile.subtext
        p.alignment = PP_ALIGN.CENTER
        _style_run(p.runs[0], size=Pt(9), color=theme.PALETTE["text_muted"])


def draw_bullet_list(slide, x: Emu, y: Emu, w: Emu, h: Emu,
                     bullets: Iterable[Bullet]) -> None:
    """Stack of body-text bullets inside the given rectangle."""
    tb = slide.shapes.add_textbox(x + Pt(8), y + Pt(8), w - Pt(16), h - Pt(16))
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for b in bullets:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.text = f"• {b.text}"
        p.space_after = Pt(6)
        _style_run(p.runs[0], size=Pt(11), color=theme.PALETTE["text_dark"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_slide_components.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/render/slide_components.py tests/unit/test_slide_components.py
git commit -m "feat(render): slide-component primitives (header, footer, container, tile, bullets)"
```

---

## Task 12: Native chart renderer (6 chart kinds → python-pptx)

**Files:**
- Create: `src/kelp_teaser/render/charts.py`
- Create: `tests/unit/test_charts.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_charts.py`:

```python
from pptx import Presentation
from pptx.util import Inches

from kelp_teaser.render import theme
from kelp_teaser.render.charts import render_chart
from kelp_teaser.schemas.slide import ChartSeries, ChartSpec


def _blank_slide():
    prs = Presentation()
    prs.slide_width = theme.SLIDE_W
    prs.slide_height = theme.SLIDE_H
    return prs, prs.slides.add_slide(prs.slide_layouts[6])


def test_render_revenue_bar_chart():
    prs, slide = _blank_slide()
    spec = ChartSpec(
        chart_kind="revenue_growth_bar",
        title="Revenue",
        categories=["FY22", "FY23", "FY24"],
        series=[ChartSeries(name="Revenue (₹ Cr)", values=[300, 380, 450])],
        source_id="doc:r.pdf#p12",
    )
    render_chart(slide, Inches(1), Inches(2), Inches(8), Inches(4), spec)
    chart_shapes = [s for s in slide.shapes if s.has_chart]
    assert len(chart_shapes) == 1


def test_render_segment_mix_donut():
    prs, slide = _blank_slide()
    spec = ChartSpec(
        chart_kind="segment_mix_donut",
        title="Segment mix",
        categories=["Lecithin", "Phospholipids", "Other"],
        series=[ChartSeries(name="Share", values=[55, 30, 15])],
        source_id="doc:r.pdf#p15",
    )
    render_chart(slide, Inches(1), Inches(2), Inches(5), Inches(4), spec)
    chart_shapes = [s for s in slide.shapes if s.has_chart]
    assert len(chart_shapes) == 1


def test_render_unknown_chart_kind_raises():
    import pytest
    prs, slide = _blank_slide()

    # Construct invalid spec via dict (bypass enum) — should fail upstream, but
    # render_chart itself should also reject if somehow reached.
    with pytest.raises(ValueError):
        render_chart(slide, Inches(1), Inches(2), Inches(5), Inches(4),
                     spec=None)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_charts.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `render/charts.py`**

Create `src/kelp_teaser/render/charts.py`:

```python
"""Native python-pptx chart renderer for the 6 supported chart kinds."""
from __future__ import annotations

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.util import Emu

from kelp_teaser.schemas.plan import ChartKind
from kelp_teaser.schemas.slide import ChartSpec

_KIND_TO_XL: dict[ChartKind, int] = {
    ChartKind.revenue_growth_bar: XL_CHART_TYPE.COLUMN_CLUSTERED,
    ChartKind.revenue_growth_line: XL_CHART_TYPE.LINE,
    ChartKind.segment_mix_donut: XL_CHART_TYPE.DOUGHNUT,
    ChartKind.margin_trend_line: XL_CHART_TYPE.LINE,
    ChartKind.geo_split_stacked_bar: XL_CHART_TYPE.COLUMN_STACKED,
    ChartKind.channel_mix_donut: XL_CHART_TYPE.DOUGHNUT,
}


def render_chart(slide, x: Emu, y: Emu, w: Emu, h: Emu, spec: ChartSpec) -> None:
    """Render a native PowerPoint chart onto `slide` per `spec`."""
    if spec is None or not isinstance(spec, ChartSpec):
        raise ValueError("render_chart requires a ChartSpec instance")

    xl_kind = _KIND_TO_XL.get(spec.chart_kind)
    if xl_kind is None:
        raise ValueError(f"unsupported chart kind: {spec.chart_kind!r}")

    data = CategoryChartData()
    data.categories = spec.categories
    for series in spec.series:
        data.add_series(series.name, series.values)

    chart = slide.shapes.add_chart(xl_kind, x, y, w, h, data).chart
    chart.has_title = bool(spec.title)
    if spec.title:
        chart.chart_title.text_frame.text = spec.title

    if spec.chart_kind in (ChartKind.segment_mix_donut, ChartKind.channel_mix_donut):
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.RIGHT
        chart.legend.include_in_layout = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_charts.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/render/charts.py tests/unit/test_charts.py
git commit -m "feat(render): native chart renderer for 6 chart kinds"
```

---

## Task 13: Deck renderer (compose slides from `ComposedSlide[]`)

**Files:**
- Create: `src/kelp_teaser/render/deck.py`
- Create: `tests/fixtures/ksolves_minimal.py`
- Create: `tests/unit/test_deck_render.py`

- [ ] **Step 1: Write the fixture**

Create `tests/fixtures/ksolves_minimal.py`:

```python
"""Minimal fixture: three ComposedSlides with every section kind exercised at least once."""
from __future__ import annotations

from kelp_teaser.schemas.slide import (
    Bullet,
    ChartSeries,
    ChartSpec,
    ComposedSection,
    ComposedSlide,
    MetricTile,
)


def three_slides() -> list[ComposedSlide]:
    return [
        ComposedSlide(
            index=0,
            title="Business Profile",
            sections=[
                ComposedSection(
                    kind="bullet_list",
                    heading="Overview",
                    bullets=[
                        Bullet(text="Mid-cap technology services player",
                               source_id="doc:onepager.md"),
                        Bullet(text="Operations across India and the US",
                               source_id="web:tavily:https://example.com"),
                    ],
                ),
                ComposedSection(
                    kind="metric_tile",
                    metrics=[
                        MetricTile(value="600+", label="Customers",
                                   source_id="doc:onepager.md"),
                        MetricTile(value="22%", label="EBITDA Margin",
                                   source_id="doc:onepager.md"),
                        MetricTile(value="₹450 Cr", label="Revenue FY24",
                                   source_id="doc:onepager.md"),
                    ],
                ),
            ],
        ),
        ComposedSlide(
            index=1,
            title="Financial Performance",
            sections=[
                ComposedSection(
                    kind="chart",
                    heading="Revenue trajectory",
                    chart=ChartSpec(
                        chart_kind="revenue_growth_bar",
                        title="Revenue (₹ Cr)",
                        categories=["FY22", "FY23", "FY24"],
                        series=[ChartSeries(name="Revenue", values=[300, 380, 450])],
                        source_id="doc:onepager.md",
                    ),
                ),
                ComposedSection(
                    kind="bullet_list",
                    bullets=[Bullet(text="35% revenue from exports",
                                    source_id="doc:onepager.md")],
                ),
            ],
        ),
        ComposedSlide(
            index=2,
            title="Investment Thesis",
            sections=[
                ComposedSection(
                    kind="bullet_list",
                    bullets=[
                        Bullet(text="Strong recurring revenue mix",
                               source_id="doc:onepager.md"),
                        Bullet(text="Industry-leading retention",
                               source_id="doc:onepager.md"),
                    ],
                ),
            ],
        ),
    ]
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_deck_render.py`:

```python
from pptx import Presentation

from kelp_teaser.render.deck import render_deck
from tests.fixtures.ksolves_minimal import three_slides


def test_render_deck_writes_three_slides(tmp_path):
    out = tmp_path / "teaser.pptx"
    render_deck(slides=three_slides(), codename="Project Halo", out_path=out)
    assert out.exists()
    prs = Presentation(str(out))
    assert len(prs.slides) == 3


def test_render_deck_includes_footer_text_on_every_slide(tmp_path):
    out = tmp_path / "teaser.pptx"
    render_deck(slides=three_slides(), codename="Project Halo", out_path=out)
    prs = Presentation(str(out))
    from kelp_teaser.render import theme
    for s in prs.slides:
        texts = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame]
        assert any(theme.FOOTER_TEXT in t for t in texts)


def test_render_deck_uses_codename_in_header(tmp_path):
    out = tmp_path / "teaser.pptx"
    render_deck(slides=three_slides(), codename="Project Halo", out_path=out)
    prs = Presentation(str(out))
    first = prs.slides[0]
    texts = [sh.text_frame.text for sh in first.shapes if sh.has_text_frame]
    assert any("Project Halo" in t for t in texts)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_deck_render.py -v`
Expected: ImportError on `render_deck`.

- [ ] **Step 4: Implement `render/deck.py`**

Create `src/kelp_teaser/render/deck.py`:

```python
"""Render a list of ComposedSlide objects into a .pptx file.

The renderer is dumb on purpose: it only knows how to draw what each
ComposedSection says. All content decisions happen upstream in the agents.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from kelp_teaser.render import theme
from kelp_teaser.render.charts import render_chart
from kelp_teaser.render.slide_components import (
    add_footer,
    add_header,
    draw_bullet_list,
    draw_container,
    draw_metric_tile,
)
from kelp_teaser.schemas.plan import ComponentKind
from kelp_teaser.schemas.slide import ComposedSection, ComposedSlide


def render_deck(*, slides: list[ComposedSlide], codename: str, out_path: Path) -> Path:
    """Render the deck. Returns the saved path."""
    prs = Presentation()
    prs.slide_width = theme.SLIDE_W
    prs.slide_height = theme.SLIDE_H

    for composed in sorted(slides, key=lambda s: s.index):
        _render_slide(prs, composed, codename)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return out_path


def _render_slide(prs, composed: ComposedSlide, codename: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = theme.PALETTE["bg_slide"]

    add_header(slide, codename=codename, subtitle=composed.title)
    add_footer(slide)

    # Below the header, place sections top-to-bottom in equal rows.
    n = len(composed.sections)
    row_h = (theme.SLIDE_H - theme.HEADER_HEIGHT - Inches(0.6)) / max(n, 1)
    y_cursor = theme.HEADER_HEIGHT + Inches(0.2)

    for section in composed.sections:
        _render_section(slide, section,
                        x=theme.MARGIN, y=y_cursor,
                        w=theme.CONTENT_W, h=row_h - Inches(0.1))
        y_cursor += row_h


def _render_section(slide, section: ComposedSection, *, x, y, w, h) -> None:
    if section.kind == ComponentKind.bullet_list:
        draw_container(slide, x, y, w, h, title=section.heading)
        draw_bullet_list(slide, x, y + Inches(0.4), w, h - Inches(0.4), section.bullets)

    elif section.kind == ComponentKind.metric_tile:
        # Equal horizontal split across N tiles.
        n = max(len(section.metrics), 1)
        tile_w = (w - (n - 1) * theme.GUTTER) / n
        cx = x
        for tile in section.metrics:
            draw_metric_tile(slide, cx, y, tile_w, h, tile)
            cx += tile_w + theme.GUTTER

    elif section.kind == ComponentKind.chart and section.chart is not None:
        draw_container(slide, x, y, w, h, title=section.heading)
        render_chart(slide,
                     x + Inches(0.2), y + Inches(0.5),
                     w - Inches(0.4), h - Inches(0.6),
                     section.chart)

    elif section.kind == ComponentKind.hero_image and section.image is not None:
        # Minimal v2 image rendering: insert the local file at full section size.
        slide.shapes.add_picture(section.image.path, x, y, width=w, height=h)

    elif section.kind == ComponentKind.product_grid:
        draw_container(slide, x, y, w, h, title=section.heading or "Portfolio")
        draw_bullet_list(slide, x, y + Inches(0.4), w, h - Inches(0.4), section.bullets)

    elif section.kind == ComponentKind.kpi_strip:
        # Render as horizontal metric tiles (alias of metric_tile layout).
        n = max(len(section.metrics), 1)
        tile_w = (w - (n - 1) * theme.GUTTER) / n
        cx = x
        for tile in section.metrics:
            draw_metric_tile(slide, cx, y, tile_w, h, tile)
            cx += tile_w + theme.GUTTER

    elif section.kind == ComponentKind.quadrant:
        # 2×2 bullet quadrants. Caller must pass 4 bullets to fill all quadrants.
        draw_container(slide, x, y, w, h, title=section.heading)
        half_w = (w - theme.GUTTER) / 2
        half_h = (h - theme.GUTTER - Inches(0.4)) / 2
        cy0 = y + Inches(0.4)
        positions = [
            (x, cy0),
            (x + half_w + theme.GUTTER, cy0),
            (x, cy0 + half_h + theme.GUTTER),
            (x + half_w + theme.GUTTER, cy0 + half_h + theme.GUTTER),
        ]
        for (px, py), bullet in zip(positions, section.bullets[:4]):
            draw_bullet_list(slide, px, py, half_w, half_h, [bullet])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_deck_render.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/render/deck.py tests/fixtures/ksolves_minimal.py tests/unit/test_deck_render.py
git commit -m "feat(render): deck renderer composing ComposedSlide[] into .pptx"
```

---

## Task 14: Citations document renderer (structured Word table)

**Files:**
- Create: `src/kelp_teaser/render/citations_doc.py`
- Create: `tests/unit/test_citations_doc.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_citations_doc.py`:

```python
from docx import Document

from kelp_teaser.render.citations_doc import render_citations_doc
from kelp_teaser.schemas.citations import CitationRow, CitationTable


def _sample_table() -> CitationTable:
    return CitationTable(rows=[
        CitationRow(slide_index=0, claim="Revenue ₹450 Cr in FY24",
                    source_id="doc:report.pdf#p12",
                    verbatim_quote="Total revenue stood at ₹450 crore",
                    confidence="High"),
        CitationRow(slide_index=1, claim="35% revenue from exports",
                    source_id="web:tavily:https://example.com/about",
                    verbatim_quote="Exports comprise about a third of revenue",
                    confidence="Medium"),
    ])


def test_render_citations_doc_creates_file(tmp_path):
    out = tmp_path / "citations.docx"
    render_citations_doc(_sample_table(), out)
    assert out.exists()


def test_render_citations_doc_writes_a_table(tmp_path):
    out = tmp_path / "citations.docx"
    render_citations_doc(_sample_table(), out)
    doc = Document(str(out))
    assert len(doc.tables) >= 1
    table = doc.tables[0]
    # Header row + 2 data rows
    assert len(table.rows) == 3
    # 5 columns: # / Slide / Claim / Source / Quote / Confidence  → 6 columns
    assert len(table.rows[0].cells) == 6


def test_render_citations_doc_includes_quote(tmp_path):
    out = tmp_path / "citations.docx"
    render_citations_doc(_sample_table(), out)
    doc = Document(str(out))
    body_text = "\n".join(p.text for p in doc.paragraphs)
    table_text = "\n".join(
        cell.text for row in doc.tables[0].rows for cell in row.cells
    )
    full = body_text + "\n" + table_text
    assert "Total revenue stood at ₹450 crore" in full
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_citations_doc.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `render/citations_doc.py`**

Create `src/kelp_teaser/render/citations_doc.py`:

```python
"""Citations document renderer: structured Word table with one row per claim."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt

from kelp_teaser.schemas.citations import CitationTable

_HEADERS = ("#", "Slide", "Claim", "Source", "Verbatim Quote", "Confidence")


def render_citations_doc(table: CitationTable, out_path: Path) -> Path:
    doc = Document()

    title = doc.add_heading("Citation Audit", level=1)
    title.runs[0].font.size = Pt(18)

    doc.add_paragraph(
        "Every claim on the teaser deck below maps to a source document or web "
        "reference. Verbatim quotes are reproduced where available."
    )

    word_table = doc.add_table(rows=1, cols=len(_HEADERS))
    word_table.style = "Light Grid Accent 1"
    for i, header in enumerate(_HEADERS):
        cell = word_table.rows[0].cells[i]
        cell.text = header
        for run in cell.paragraphs[0].runs:
            run.bold = True

    for i, row in enumerate(table.rows, start=1):
        cells = word_table.add_row().cells
        cells[0].text = str(i)
        cells[1].text = str(row.slide_index + 1)
        cells[2].text = row.claim
        cells[3].text = row.source_id
        cells[4].text = row.verbatim_quote
        cells[5].text = row.confidence

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_citations_doc.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/render/citations_doc.py tests/unit/test_citations_doc.py
git commit -m "feat(render): citations doc with structured 6-column claim table"
```

---

## Task 15: Migrate inputs and archive v1 outputs (no code change to v1)

**Files:**
- Move: `examples/*` → `data/inputs/*`
- Delete or archive: root-level `*_ANALYSIS.json`, `*_FULL_CONTEXT.txt`, `Final_Submissions/`

- [ ] **Step 1: List current root-level v1 artifacts**

Run:
```bash
ls -1 *_ANALYSIS.json *_FULL_CONTEXT.txt 2>/dev/null || true
ls -1 examples/ 2>/dev/null || true
ls -1 Final_Submissions/ 2>/dev/null || true
```
Expected: prints the files we will move/archive. No surprises (no in-progress work the user hasn't mentioned).

- [ ] **Step 2: Move input examples to `data/inputs/`**

Run:
```bash
# Each example becomes a folder under data/inputs/ named after the company.
# Single-file examples become a folder containing that one file.
mkdir -p data/inputs
git mv examples/Gati-OnePager.md data/inputs/Gati/Gati-OnePager.md 2>/dev/null || mv examples/Gati-OnePager.md data/inputs/Gati/Gati-OnePager.md
# (Repeat for any other files/folders in examples/; the engineer should glob and process them.)
# For any folder under examples/, move it as a unit:
for d in examples/*/; do
  base="$(basename "$d")"
  mkdir -p "data/inputs/$base"
  git mv "$d"* "data/inputs/$base/" 2>/dev/null || mv "$d"* "data/inputs/$base/"
done
rmdir examples 2>/dev/null || true
```

- [ ] **Step 3: Archive v1 root outputs into an `archive/` directory (do not delete)**

Run:
```bash
mkdir -p archive/v1
git mv *_ANALYSIS.json archive/v1/ 2>/dev/null || mv *_ANALYSIS.json archive/v1/ 2>/dev/null || true
git mv *_FULL_CONTEXT.txt archive/v1/ 2>/dev/null || mv *_FULL_CONTEXT.txt archive/v1/ 2>/dev/null || true
git mv Final_Submissions archive/v1/Final_Submissions 2>/dev/null || mv Final_Submissions archive/v1/Final_Submissions 2>/dev/null || true
```

- [ ] **Step 4: Verify v1 scripts at the root still import their inputs**

Note: v1 scripts (`main.py`, `analyze.py`, etc.) reference `examples/` and write `*_ANALYSIS.json` to repo root. They will break after this migration. That is expected — v1 is being retired. Do **not** fix them; they will be deleted in Phase B once v2 is end-to-end.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: migrate v1 inputs to data/inputs and archive v1 outputs"
```

---

## Task 16: Full test-suite green check and Phase A close-out

**Files:**
- (no new files)

- [ ] **Step 1: Run the full unit test suite**

Run: `pytest -v`
Expected: every test passes. No collection errors.

- [ ] **Step 2: Confirm the package imports cleanly**

Run:
```bash
python -c "
import kelp_teaser.config as c
from kelp_teaser.schemas.facts import Fact
from kelp_teaser.schemas.plan import DeckPlan, Sector, ChartKind, ComponentKind
from kelp_teaser.schemas.slide import ComposedSlide, ChartSpec, MetricTile, Bullet
from kelp_teaser.schemas.critic import CriticReport
from kelp_teaser.schemas.citations import CitationTable
from kelp_teaser.tools import llm, prompt_loader, pdf_parser, excel_parser, web_search, image_search
from kelp_teaser.render import theme, slide_components, charts, deck, citations_doc
print('OK')
"
```
Expected: prints `OK`.

- [ ] **Step 3: Render the fixture deck end-to-end (no agents yet)**

Run:
```bash
python -c "
from pathlib import Path
from tests.fixtures.ksolves_minimal import three_slides
from kelp_teaser.render.deck import render_deck
from kelp_teaser.render.citations_doc import render_citations_doc
from kelp_teaser.schemas.citations import CitationRow, CitationTable

out_dir = Path('data/outputs/_phase_a_smoke')
render_deck(slides=three_slides(), codename='Project Halo',
            out_path=out_dir / 'teaser.pptx')
table = CitationTable(rows=[
    CitationRow(slide_index=0, claim='Revenue ₹450 Cr in FY24',
                source_id='doc:onepager.md',
                verbatim_quote='Total revenue stood at ₹450 crore',
                confidence='High'),
])
render_citations_doc(table, out_dir / 'citations.docx')
print(f'Wrote {out_dir}/teaser.pptx and citations.docx')
"
```
Expected: file paths printed; both files exist and open in PowerPoint/Word.

- [ ] **Step 4: Commit close-out marker**

```bash
git commit --allow-empty -m "chore: phase A foundation complete (schemas + tools + renderers)"
```

---

## Phase A Acceptance Criteria

By the end of this plan, the engineer should have:

1. `pyproject.toml` installed, all dev dependencies present, `pytest -v` green.
2. `src/kelp_teaser/` package importable, with `config`, `schemas/`, `tools/`, `render/` subpackages populated.
3. Pydantic schemas enforcing every spec invariant: `Fact` and `Bullet`/`MetricTile` reject empty `source_id`; `DeckPlan` enforces exactly 3 slides; `SectionPlan(kind=chart)` requires `chart_spec`.
4. Empty prompt files exist at `prompts/<name>.md` for all 7 agents (Phase B fills them).
5. Tool wrappers (PDF, Excel, Tavily, Pexels, LLM, prompt loader) are unit-testable for their pure parts and fail soft (return empty / log) for their network parts.
6. Renderers (theme, slide components, charts, deck, citations doc) produce a valid `.pptx` and `.docx` from a fixture `ComposedSlide[]` with no agent code involved.
7. v1 inputs moved to `data/inputs/`; v1 outputs archived under `archive/v1/`.
8. Phase B (agents + LangGraph) can begin without touching anything outside `src/kelp_teaser/agents/` and `src/kelp_teaser/graph/`.
