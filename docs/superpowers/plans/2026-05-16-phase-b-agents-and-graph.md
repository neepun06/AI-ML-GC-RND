# Phase B: Agents, LangGraph Wiring, and CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the Phase A foundation (schemas + tools + renderers) and build the full agentic pipeline on top of it: 9 specialized agents, LangGraph state machine with parallel Composer fan-out, a CLI entrypoint, and 7 prompt files. After this phase, `kelp-teaser run <company-folder>` produces a real anonymized blind-teaser `.pptx` and structured citations `.docx` end-to-end from Gemini API calls.

**Architecture:** A `GraphState` Pydantic model carries everything between nodes. LangGraph wires the nodes in this order: Ingestor → Researcher → SectorClassifier → Planner → [Composer × 3 in parallel via `Send`] → Anonymizer → Critic (single pass) → CitationTracker → DeckRenderer → CitationDocRenderer. Each agent is a pure function `(GraphState) → partial GraphState` in its own file. Every LLM call goes through `tools/llm.py`. All intermediate state and an aggregated trace land under `data/outputs/{company}_{run_id}/intermediate/`.

**Tech Stack:** LangGraph 0.2.x, Pydantic v2, google-genai SDK (Gemini Flash + Pro), python-pptx, python-docx, Jinja2 prompts, Tavily, Pexels, LlamaParse. Builds on the `src/kelp_teaser/` package shipped in Phase A.

**Reference spec:** [docs/superpowers/specs/2026-05-16-agentic-teaser-pipeline-design.md](../specs/2026-05-16-agentic-teaser-pipeline-design.md)
**Builds on:** [docs/superpowers/plans/2026-05-16-phase-a-foundation.md](2026-05-16-phase-a-foundation.md) (merged to main as `f7116f9`)

---

## File Structure (created in this phase)

```
src/kelp_teaser/
├── graph/
│   ├── __init__.py
│   ├── state.py            # GraphState Pydantic model
│   ├── build_graph.py      # LangGraph topology with conditional/parallel edges
│   └── trace.py            # writes per-step JSON + run-level trace.json
├── agents/
│   ├── __init__.py
│   ├── ingestor.py
│   ├── researcher.py
│   ├── sector_classifier.py
│   ├── planner.py
│   ├── composer.py
│   ├── chart_designer.py
│   ├── image_curator.py
│   ├── anonymizer.py
│   ├── critic.py
│   └── citation_tracker.py
└── cli.py                  # `kelp-teaser run <input-folder>` entrypoint

prompts/                    # the 7 placeholder files get real content
├── sector_classifier.md
├── planner.md
├── composer.md
├── chart_designer.md
├── image_curator.md
├── anonymizer.md
└── critic.md

tests/
├── unit/
│   ├── test_graph_state.py
│   ├── test_trace.py
│   ├── test_ingestor.py
│   ├── test_researcher_helpers.py
│   ├── test_sector_classifier_helpers.py
│   ├── test_planner_helpers.py
│   ├── test_composer_helpers.py
│   ├── test_chart_designer.py
│   ├── test_image_curator_helpers.py
│   ├── test_anonymizer.py
│   ├── test_critic.py
│   ├── test_citation_tracker.py
│   ├── test_build_graph.py
│   └── test_cli_smoke.py
└── fixtures/
    ├── ksolves_data_pack/  # tiny fixture data pack on disk
    │   └── Ksolves-OnePager.md
    └── stub_llm.py         # monkeypatch helper that fakes Gemini calls
```

---

## Conventions used in this plan

- **Stub LLM in unit tests.** The `tests/fixtures/stub_llm.py` helper provides `patch_llm(monkeypatch, responses)` that monkey-patches `kelp_teaser.tools.llm.complete_text` and `complete_json` with canned responses. No unit test hits the Gemini API. There is exactly ONE manual end-to-end test (Task 26) that hits live APIs; it's not in the pytest suite.
- **Trace folder.** All agents accept an optional `trace_writer` and write their input/output JSON to `data/outputs/<run_id>/intermediate/<step:02d>_<agent>.json`. Tests pass a no-op trace writer.
- **No mocking of internal Pydantic types.** Tests build real `IngestedDoc`, `WebSnippet`, `DeckPlan`, etc., from fixtures.
- **Each agent has signature** `def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict`. Returns the dict of fields to merge into state (LangGraph's pattern). No mutation of the input state.

---

## Task 1: Patch `CostTracker` for thread safety

**Why first:** The Composer fans out 3 calls in parallel via LangGraph `Send` (Task 17). The current `CostTracker.record()` in `src/kelp_teaser/tools/llm.py` uses bare `list.append` and `defaultdict[float] +=`, both unsafe under concurrent writes. Fix before any parallel code lands.

**Files:**
- Modify: `src/kelp_teaser/tools/llm.py`
- Modify: `tests/unit/test_llm.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_llm.py`:

```python
import threading

from kelp_teaser.tools.llm import CostTracker, GeminiCall


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_llm.py::TestCostTrackerThreadSafety -v`
Expected: at least one test FAILS (lost updates in `calls` list or `by_model` totals). On Windows, GIL may mask some races, but the assertion may still fail intermittently.

- [ ] **Step 3: Add a lock to `CostTracker`**

Modify `src/kelp_teaser/tools/llm.py`. Change the `CostTracker` dataclass to:

```python
import threading

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
```

Add `import threading` near the top of the file alongside the other stdlib imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_llm.py -v`
Expected: 5 passed (3 original + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/tools/llm.py tests/unit/test_llm.py
git commit -m "fix(tools): make CostTracker thread-safe with internal lock"
```

---

## Task 2: `GraphState` Pydantic model

**Files:**
- Create: `src/kelp_teaser/graph/__init__.py`
- Create: `src/kelp_teaser/graph/state.py`
- Create: `tests/unit/test_graph_state.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_graph_state.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_graph_state.py -v`
Expected: ImportError on `kelp_teaser.graph.state`.

- [ ] **Step 3: Implement `graph/state.py`**

Create `src/kelp_teaser/graph/__init__.py` empty.

Create `src/kelp_teaser/graph/state.py`:

```python
"""GraphState: the single Pydantic object passed through every LangGraph node."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from kelp_teaser.schemas.citations import CitationTable
from kelp_teaser.schemas.critic import CriticReport, Substitution
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.schemas.plan import DeckPlan, Sector
from kelp_teaser.schemas.slide import ComposedSlide


class GraphState(BaseModel):
    # Input (set by CLI before the graph runs)
    company_name: str = Field(min_length=1)
    input_path: Path
    run_id: str = Field(min_length=1)

    # Filled by Ingestor / Researcher
    docs: list[IngestedDoc] = Field(default_factory=list)
    web_snippets: list[WebSnippet] = Field(default_factory=list)
    planner_brief: str = ""

    # Filled by SectorClassifier
    sector: Sector | None = None
    sector_confidence: float | None = None
    sub_sector: str = ""

    # Filled by Planner
    plan: DeckPlan | None = None

    # Filled by Composer (parallel fan-in via dict-merge)
    composed_slides: dict[int, ComposedSlide] = Field(default_factory=dict)

    # Filled by Anonymizer
    anonymization_log: list[Substitution] = Field(default_factory=list)

    # Filled by Critic
    critic_report: CriticReport | None = None

    # Filled by CitationTracker
    citation_table: CitationTable | None = None

    # Output paths (set by renderers)
    pptx_path: Path | None = None
    citations_path: Path | None = None
    trace_path: Path | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_graph_state.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/graph/__init__.py src/kelp_teaser/graph/state.py tests/unit/test_graph_state.py
git commit -m "feat(graph): GraphState Pydantic model for end-to-end pipeline state"
```

---

## Task 3: Trace writer (per-step JSON dumps + run-level trace.json)

**Files:**
- Create: `src/kelp_teaser/graph/trace.py`
- Create: `tests/unit/test_trace.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_trace.py`:

```python
import json
from pathlib import Path

from kelp_teaser.graph.trace import TraceWriter


def test_trace_writer_writes_step_files(tmp_path):
    writer = TraceWriter(run_dir=tmp_path)
    writer.write_step("ingestor", {"docs_count": 3})
    writer.write_step("researcher", {"snippets_count": 7})

    files = sorted((tmp_path / "intermediate").glob("*.json"))
    assert len(files) == 2
    assert files[0].name == "00_ingestor.json"
    assert files[1].name == "01_researcher.json"

    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["agent"] == "ingestor"
    assert payload["data"] == {"docs_count": 3}


def test_trace_writer_finalize_writes_summary(tmp_path):
    writer = TraceWriter(run_dir=tmp_path)
    writer.write_step("ingestor", {"docs_count": 3})
    writer.write_step("researcher", {"snippets_count": 7})
    writer.add_cost(0.05)
    writer.add_cost(0.12)
    writer.finalize()

    trace = json.loads((tmp_path / "trace.json").read_text(encoding="utf-8"))
    assert trace["total_cost_usd"] == 0.17
    assert len(trace["steps"]) == 2
    assert trace["steps"][0]["agent"] == "ingestor"


def test_trace_writer_no_op_when_no_run_dir():
    writer = TraceWriter(run_dir=None)
    writer.write_step("anything", {"x": 1})
    writer.add_cost(0.1)
    writer.finalize()  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_trace.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `graph/trace.py`**

Create `src/kelp_teaser/graph/trace.py`:

```python
"""TraceWriter: persists per-agent JSON dumps and a top-level trace.json."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class TraceWriter:
    """Writes intermediate/<NN>_<agent>.json files and a final trace.json.

    When `run_dir` is None, all methods are no-ops. This lets tests pass
    `TraceWriter(run_dir=None)` to disable trace writing.
    """

    def __init__(self, run_dir: Path | None) -> None:
        self.run_dir = run_dir
        self.steps: list[dict[str, Any]] = []
        self.costs: list[float] = []
        self._started_at = time.time()
        if run_dir is not None:
            (run_dir / "intermediate").mkdir(parents=True, exist_ok=True)

    def write_step(self, agent: str, data: dict[str, Any]) -> None:
        idx = len(self.steps)
        payload = {
            "step": idx,
            "agent": agent,
            "elapsed_s": round(time.time() - self._started_at, 3),
            "data": data,
        }
        self.steps.append(payload)
        if self.run_dir is None:
            return
        out = self.run_dir / "intermediate" / f"{idx:02d}_{agent}.json"
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def add_cost(self, usd: float) -> None:
        self.costs.append(usd)

    def finalize(self) -> Path | None:
        if self.run_dir is None:
            return None
        out = self.run_dir / "trace.json"
        out.write_text(
            json.dumps(
                {
                    "total_cost_usd": round(sum(self.costs), 4),
                    "total_elapsed_s": round(time.time() - self._started_at, 3),
                    "steps": self.steps,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_trace.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/graph/trace.py tests/unit/test_trace.py
git commit -m "feat(graph): TraceWriter for per-step JSON and run-level trace.json"
```

---

## Task 4: Stub-LLM test fixture

**Files:**
- Create: `tests/fixtures/stub_llm.py`

- [ ] **Step 1: Implement the stub helper**

Create `tests/fixtures/stub_llm.py`:

```python
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
```

- [ ] **Step 2: Sanity check it imports cleanly**

Run: `python -c "from tests.fixtures.stub_llm import patch_llm; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/stub_llm.py
git commit -m "test(fixtures): stub_llm helper for monkeypatching Gemini calls"
```

---

## Task 5: Ingestor agent (no LLM)

**Files:**
- Create: `src/kelp_teaser/agents/__init__.py`
- Create: `src/kelp_teaser/agents/ingestor.py`
- Create: `tests/fixtures/ksolves_data_pack/Ksolves-OnePager.md`
- Create: `tests/unit/test_ingestor.py`

- [ ] **Step 1: Write the data-pack fixture**

Create `tests/fixtures/ksolves_data_pack/Ksolves-OnePager.md`:

```markdown
# Ksolves One-Pager

Ksolves is a mid-cap IT services company headquartered in Noida, India.
Revenue FY24: ₹450 Cr. EBITDA margin: 22%. Customers: 600+.
Operates across India and the US.
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/test_ingestor.py`:

```python
from pathlib import Path

from kelp_teaser.agents.ingestor import run as run_ingestor
from kelp_teaser.graph.state import GraphState

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ksolves_data_pack"


def _state(input_path: Path) -> GraphState:
    return GraphState(company_name="Ksolves", input_path=input_path, run_id="t1")


def test_ingestor_reads_markdown_file():
    state = _state(FIXTURE)
    result = run_ingestor(state)
    docs = result["docs"]
    assert len(docs) == 1
    assert docs[0].filename == "Ksolves-OnePager.md"
    assert docs[0].source_id == "doc:Ksolves-OnePager.md"
    assert "Ksolves is a mid-cap IT services" in docs[0].text


def test_ingestor_skips_hidden_and_unknown_files(tmp_path):
    (tmp_path / ".hidden.md").write_text("ignore me")
    (tmp_path / "good.md").write_text("read me")
    (tmp_path / "unknown.xyz").write_text("skip me")
    state = _state(tmp_path)
    result = run_ingestor(state)
    filenames = sorted(d.filename for d in result["docs"])
    assert filenames == ["good.md"]


def test_ingestor_accepts_single_file_path(tmp_path):
    p = tmp_path / "solo.md"
    p.write_text("solo content")
    state = _state(p)
    result = run_ingestor(state)
    assert len(result["docs"]) == 1
    assert result["docs"][0].filename == "solo.md"


def test_ingestor_returns_empty_docs_when_folder_empty(tmp_path):
    state = _state(tmp_path)
    result = run_ingestor(state)
    assert result["docs"] == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_ingestor.py -v`
Expected: ImportError on `kelp_teaser.agents.ingestor`.

- [ ] **Step 4: Implement `agents/ingestor.py`**

Create `src/kelp_teaser/agents/__init__.py` empty.

Create `src/kelp_teaser/agents/ingestor.py`:

```python
"""Ingestor: walks the input path, parses every supported file into an IngestedDoc.

No LLM call. Pure I/O + parsing.
"""
from __future__ import annotations

import logging
from pathlib import Path

from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.facts import IngestedDoc
from kelp_teaser.tools.excel_parser import flatten_workbook
from kelp_teaser.tools.pdf_parser import parse_pdf

log = logging.getLogger(__name__)

_TEXT_SUFFIXES = {".md", ".txt"}
_EXCEL_SUFFIXES = {".xlsx", ".xls"}
_PDF_SUFFIXES = {".pdf"}


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    docs: list[IngestedDoc] = []
    path = state.input_path

    if path.is_file():
        candidates = [path]
    elif path.is_dir():
        candidates = sorted(p for p in path.iterdir()
                            if p.is_file() and not p.name.startswith("."))
    else:
        log.warning("Ingestor: input_path %s is neither file nor directory", path)
        candidates = []

    for f in candidates:
        text = _read_one(f)
        if not text:
            continue
        docs.append(IngestedDoc(
            source_id=f"doc:{f.name}",
            filename=f.name,
            text=text,
        ))

    if trace_writer is not None:
        trace_writer.write_step("ingestor", {
            "docs_count": len(docs),
            "filenames": [d.filename for d in docs],
        })

    return {"docs": docs}


def _read_one(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _TEXT_SUFFIXES:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1", errors="replace")
    if suffix in _EXCEL_SUFFIXES:
        try:
            return flatten_workbook(str(path))
        except Exception as e:  # noqa: BLE001
            log.error("Excel parse failed for %s: %s", path, e)
            return ""
    if suffix in _PDF_SUFFIXES:
        return parse_pdf(path)
    log.info("Ingestor: skipping unsupported file %s", path.name)
    return ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_ingestor.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/agents/__init__.py src/kelp_teaser/agents/ingestor.py \
        tests/fixtures/ksolves_data_pack/Ksolves-OnePager.md \
        tests/unit/test_ingestor.py
git commit -m "feat(agents): Ingestor walks data pack and builds IngestedDoc list"
```

---

## Task 6: Researcher agent (Tavily + Flash summarize + planner_brief)

**Files:**
- Create: `src/kelp_teaser/agents/researcher.py`
- Create: `tests/unit/test_researcher_helpers.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_researcher_helpers.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_researcher_helpers.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `agents/researcher.py`**

Create `src/kelp_teaser/agents/researcher.py`:

```python
"""Researcher: targeted Tavily queries + Flash summarization + planner_brief."""
from __future__ import annotations

import logging

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.tools import llm, web_search

log = logging.getLogger(__name__)

_SUMMARIZE_PROMPT = (
    "Summarize the following web page into 3-6 punchy bullet points "
    "useful for M&A investment analysis of '{company}'. Keep numbers verbatim. "
    "Max 400 words.\n\nTitle: {title}\nURL: {url}\n\nCONTENT:\n{content}"
)


def default_queries(company_name: str) -> list[str]:
    return [
        f"{company_name} product portfolio technical specifications and manufacturing capacity",
        f"{company_name} recent awards certifications and client case studies 2024 2025",
        f"{company_name} revenue breakdown by geography and segment annual report",
    ]


def build_planner_brief(docs: list[IngestedDoc], snippets: list[WebSnippet]) -> str:
    parts: list[str] = []
    if docs:
        parts.append("## PRIVATE DOCUMENTS")
        for d in docs:
            parts.append(f"### {d.filename} ({d.source_id})")
            parts.append(d.text.strip())
    if snippets:
        parts.append("\n## PUBLIC WEB SNIPPETS")
        for s in snippets:
            parts.append(f"### {s.url} ({s.source_id})")
            parts.append(s.summary.strip())
    return "\n".join(parts)


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    snippets: list[WebSnippet] = []
    for query in default_queries(state.company_name):
        hits = web_search.search(query, max_results=3)
        for hit in hits:
            if not hit.url or not hit.content:
                continue
            summary = _summarize_hit(state.company_name, hit)
            snippets.append(WebSnippet(
                source_id=f"web:tavily:{hit.url}",
                url=hit.url,
                summary=summary,
                query=query,
            ))

    brief = build_planner_brief(state.docs, snippets)

    if trace_writer is not None:
        trace_writer.write_step("researcher", {
            "snippet_count": len(snippets),
            "brief_chars": len(brief),
        })

    return {"web_snippets": snippets, "planner_brief": brief}


def _summarize_hit(company: str, hit) -> str:
    prompt = _SUMMARIZE_PROMPT.format(
        company=company, title=hit.title, url=hit.url,
        content=hit.content[:8000],
    )
    try:
        return llm.complete_text(MODEL_FAST, prompt, temperature=0.2)
    except Exception as e:  # noqa: BLE001
        log.error("Researcher summarize failed for %s: %s", hit.url, e)
        return hit.content[:500]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_researcher_helpers.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/agents/researcher.py tests/unit/test_researcher_helpers.py
git commit -m "feat(agents): Researcher with Tavily queries, Flash summarization, planner_brief"
```

---

## Task 7: SectorClassifier agent + prompt

**Files:**
- Create: `src/kelp_teaser/agents/sector_classifier.py`
- Modify: `prompts/sector_classifier.md`
- Create: `tests/unit/test_sector_classifier_helpers.py`

- [ ] **Step 1: Write the prompt**

Overwrite `prompts/sector_classifier.md` with:

```markdown
You are an M&A sector classifier.

Classify the company described below into ONE of these sectors:
- Manufacturing
- SpecialtyChemicals
- D2C
- SaaS
- Pharma
- Logistics
- FinancialServices
- Consumer
- Other

Also provide a short (≤5 words) sub-sector tag and a confidence score 0.0-1.0.

## Company brief

{{ brief }}

## Response format

Respond with strictly valid JSON matching:
{
  "sector": "<one of the 9 enum values>",
  "sub_sector": "<short tag>",
  "confidence": <float 0-1>
}
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/test_sector_classifier_helpers.py`:

```python
from pathlib import Path

from kelp_teaser.agents.sector_classifier import (
    SectorClassification,
    run as run_classifier,
)
from kelp_teaser.graph.state import GraphState
from kelp_teaser.schemas.plan import Sector
from tests.fixtures.stub_llm import patch_llm


def _state(brief: str) -> GraphState:
    return GraphState(company_name="Acme", input_path=Path("."), run_id="r1",
                      planner_brief=brief)


def test_sector_classifier_returns_sector_subsector_and_confidence(monkeypatch):
    obj = SectorClassification(sector=Sector.SaaS, sub_sector="DevOps tools",
                               confidence=0.92)
    patch_llm(monkeypatch, json_responses=[obj])
    result = run_classifier(_state("Acme is a SaaS company..."))
    assert result["sector"] == Sector.SaaS
    assert result["sub_sector"] == "DevOps tools"
    assert result["sector_confidence"] == 0.92


def test_sector_classifier_passes_dict_through_schema(monkeypatch):
    patch_llm(monkeypatch, json_responses=[
        {"sector": "D2C", "sub_sector": "Wellness", "confidence": 0.75},
    ])
    result = run_classifier(_state("Brief..."))
    assert result["sector"] == Sector.D2C
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_sector_classifier_helpers.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `agents/sector_classifier.py`**

Create `src/kelp_teaser/agents/sector_classifier.py`:

```python
"""SectorClassifier: single Flash call → Sector enum + sub_sector + confidence."""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.plan import Sector
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)


class SectorClassification(BaseModel):
    sector: Sector
    sub_sector: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    prompt = load_prompt("sector_classifier").render(brief=state.planner_brief)
    try:
        result = llm.complete_json(MODEL_FAST, prompt, SectorClassification)
    except Exception as e:  # noqa: BLE001
        log.error("SectorClassifier failed, defaulting to Other: %s", e)
        result = SectorClassification(sector=Sector.Other, confidence=0.0)

    if trace_writer is not None:
        trace_writer.write_step("sector_classifier", result.model_dump())

    return {
        "sector": result.sector,
        "sub_sector": result.sub_sector,
        "sector_confidence": result.confidence,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_sector_classifier_helpers.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/agents/sector_classifier.py prompts/sector_classifier.md \
        tests/unit/test_sector_classifier_helpers.py
git commit -m "feat(agents): SectorClassifier (Flash) returns Sector + sub_sector + confidence"
```

---

## Task 8: Planner agent + prompt

**Files:**
- Create: `src/kelp_teaser/agents/planner.py`
- Modify: `prompts/planner.md`
- Create: `tests/unit/test_planner_helpers.py`

- [ ] **Step 1: Write the prompt**

Overwrite `prompts/planner.md` with:

```markdown
You are the Deck Planner for a Kelp M&A blind teaser.

## Rules

1. The output is a `DeckPlan` with EXACTLY 3 `SlidePlan`s. Not 2, not 4.
2. The deck is BLIND — assign a codename like "Project Halo", "Project Aurora", "Project Aegis". NEVER use the real company name.
3. Each slide has 1-5 `SectionPlan`s. Section `kind` must be one of: metric_tile, quadrant, chart, hero_image, bullet_list, product_grid, kpi_strip.
4. If a section's kind is `chart`, it MUST include a `chart_spec` with `chart_kind` from: revenue_growth_bar, revenue_growth_line, segment_mix_donut, margin_trend_line, geo_split_stacked_bar, channel_mix_donut.
5. If a section's kind is `hero_image`, it MUST include a non-empty `image_brief` (a short descriptive query for stock-photo search).
6. `data_hooks` is a list of short keys naming what the Composer should fetch from docs/web (e.g. "revenue_fy24", "customer_count", "certifications").
7. Pick sections that match the sector. Examples:
   - Manufacturing/SpecialtyChemicals → product_grid, metric_tile (facilities/exports), chart (revenue), hero_image (factory).
   - D2C → kpi_strip (LTV/CAC/AOV), chart (revenue or units), hero_image (product lifestyle).
   - SaaS → metric_tile (ARR/churn), chart (revenue), bullet_list (product highlights).
   - Pharma → product_grid (portfolio), metric_tile (certifications), bullet_list (R&D pipeline).
   - Logistics → metric_tile (fleet/coverage), chart (volume), bullet_list (network).
8. Slide order: Slide 1 = business overview; Slide 2 = financial/operational scale; Slide 3 = investment thesis.

## Inputs

- Sector: {{ sector }} ({{ sub_sector }})
- Company brief (codename internally only):
{{ brief }}

## Response format

Respond ONLY with valid JSON matching the `DeckPlan` schema (see schema hint appended by the runtime).
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/test_planner_helpers.py`:

```python
from pathlib import Path

from kelp_teaser.agents.planner import run as run_planner
from kelp_teaser.graph.state import GraphState
from kelp_teaser.schemas.plan import (
    ChartKind,
    ComponentKind,
    DeckPlan,
    Sector,
    SectionPlan,
    SlidePlan,
    ChartSpecSkeleton,
)
from tests.fixtures.stub_llm import patch_llm


def _state() -> GraphState:
    return GraphState(company_name="Ksolves", input_path=Path("."), run_id="r1",
                      planner_brief="Brief...", sector=Sector.SaaS,
                      sub_sector="DevOps")


def _valid_plan() -> DeckPlan:
    return DeckPlan(codename="Project Halo", slides=[
        SlidePlan(title="Overview", sections=[
            SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["summary"]),
        ]),
        SlidePlan(title="Financials", sections=[
            SectionPlan(kind=ComponentKind.chart, data_hooks=["revenue"],
                        chart_spec=ChartSpecSkeleton(chart_kind=ChartKind.revenue_growth_bar)),
        ]),
        SlidePlan(title="Thesis", sections=[
            SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["hooks"]),
        ]),
    ])


def test_planner_returns_deck_plan(monkeypatch):
    plan = _valid_plan()
    patch_llm(monkeypatch, json_responses=[plan])
    result = run_planner(_state())
    assert result["plan"].codename == "Project Halo"
    assert len(result["plan"].slides) == 3


def test_planner_renders_prompt_with_sector(monkeypatch):
    captured = {}

    def fake_complete_json(model, prompt, schema, *, temperature=0.2, tracker=None):
        captured["prompt"] = prompt
        return _valid_plan()

    import kelp_teaser.tools.llm as llm_module
    monkeypatch.setattr(llm_module, "complete_json", fake_complete_json)

    run_planner(_state())
    assert "SaaS" in captured["prompt"]
    assert "DevOps" in captured["prompt"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_planner_helpers.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `agents/planner.py`**

Create `src/kelp_teaser/agents/planner.py`:

```python
"""Planner: Pro call returning a DeckPlan with codename + 3 SlidePlans."""
from __future__ import annotations

import logging

from kelp_teaser.config import MODEL_SMART
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.plan import DeckPlan
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    sector_name = state.sector.value if state.sector is not None else "Other"
    prompt = load_prompt("planner").render(
        sector=sector_name,
        sub_sector=state.sub_sector,
        brief=state.planner_brief,
    )
    plan: DeckPlan = llm.complete_json(MODEL_SMART, prompt, DeckPlan)

    if trace_writer is not None:
        trace_writer.write_step("planner", plan.model_dump())

    return {"plan": plan}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_planner_helpers.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/agents/planner.py prompts/planner.md \
        tests/unit/test_planner_helpers.py
git commit -m "feat(agents): Planner (Pro) emits DeckPlan with codename + 3 SlidePlans"
```

---

## Task 9: ChartDesigner agent + prompt

**Files:**
- Create: `src/kelp_teaser/agents/chart_designer.py`
- Modify: `prompts/chart_designer.md`
- Create: `tests/unit/test_chart_designer.py`

- [ ] **Step 1: Write the prompt**

Overwrite `prompts/chart_designer.md` with:

```markdown
You design a single native PowerPoint chart for an M&A teaser slide.

## Inputs

- Chart kind requested: {{ chart_kind }}
- Section heading: {{ heading }}
- Data hooks: {{ data_hooks }}
- Source material (use ONLY these facts; quote numbers verbatim where possible):
{{ source_context }}

## Rules

1. Pick a clear title (≤6 words). For revenue charts include the unit (e.g. "Revenue (₹ Cr)").
2. `categories` must be 2-6 entries (years, segments, regions, etc.).
3. `series` should contain 1-3 named series. Each series has a `name` and `values` of equal length to `categories`.
4. The `source_id` field MUST be the exact source_id from the supplied source material.
5. If the underlying numbers aren't present in the source, INVENT NOTHING — return a chart with the most defensible values you can support.

## Response format

Respond with strictly valid JSON matching the `ChartSpec` schema (see schema hint appended by the runtime).
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/test_chart_designer.py`:

```python
from kelp_teaser.agents.chart_designer import design_chart
from kelp_teaser.schemas.plan import ChartKind, ChartSpecSkeleton, ComponentKind, SectionPlan
from kelp_teaser.schemas.slide import ChartSeries, ChartSpec
from tests.fixtures.stub_llm import patch_llm


def _section() -> SectionPlan:
    return SectionPlan(
        kind=ComponentKind.chart,
        data_hooks=["revenue_fy22", "revenue_fy23", "revenue_fy24"],
        chart_spec=ChartSpecSkeleton(chart_kind=ChartKind.revenue_growth_bar, title=""),
        note="",
    )


def test_design_chart_returns_chart_spec(monkeypatch):
    expected = ChartSpec(
        chart_kind=ChartKind.revenue_growth_bar,
        title="Revenue (₹ Cr)",
        categories=["FY22", "FY23", "FY24"],
        series=[ChartSeries(name="Revenue", values=[300, 380, 450])],
        source_id="doc:r.md",
    )
    patch_llm(monkeypatch, json_responses=[expected])
    out = design_chart(_section(), source_context="doc:r.md — Revenue ₹300/380/450 Cr")
    assert out.chart_kind == ChartKind.revenue_growth_bar
    assert out.categories == ["FY22", "FY23", "FY24"]
    assert out.source_id == "doc:r.md"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_chart_designer.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `agents/chart_designer.py`**

Create `src/kelp_teaser/agents/chart_designer.py`:

```python
"""ChartDesigner: Flash call that turns a chart-kind SectionPlan into a ChartSpec."""
from __future__ import annotations

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.schemas.plan import SectionPlan
from kelp_teaser.schemas.slide import ChartSpec
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt


def design_chart(section: SectionPlan, *, source_context: str) -> ChartSpec:
    if section.chart_spec is None:
        raise ValueError("design_chart requires SectionPlan.chart_spec to be set")
    prompt = load_prompt("chart_designer").render(
        chart_kind=section.chart_spec.chart_kind.value,
        heading=section.chart_spec.title or "",
        data_hooks=", ".join(section.data_hooks),
        source_context=source_context,
    )
    return llm.complete_json(MODEL_FAST, prompt, ChartSpec)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_chart_designer.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/agents/chart_designer.py prompts/chart_designer.md \
        tests/unit/test_chart_designer.py
git commit -m "feat(agents): ChartDesigner (Flash) emits ChartSpec from chart SectionPlan"
```

---

## Task 10: ImageCurator agent + prompt

**Files:**
- Create: `src/kelp_teaser/agents/image_curator.py`
- Modify: `prompts/image_curator.md`
- Create: `tests/unit/test_image_curator_helpers.py`

- [ ] **Step 1: Write the prompt**

Overwrite `prompts/image_curator.md` with:

```markdown
You write Pexels stock-image search queries for an M&A teaser slide.

## Goal

Generate 2-3 specific search queries that will return industry-appropriate, generic photos with NO visible logos, brand names, or specific people-in-suits stock cheesy aesthetics.

## Input

- Section image_brief: {{ image_brief }}
- Sector context: {{ sector }}

## Examples

- Bad: "factory", "office"
- Good: "stainless steel reactor vessel pharmaceutical plant interior",
        "automated bottling line beverage manufacturing"

## Response format

Respond with strictly valid JSON matching:
{
  "queries": ["<query1>", "<query2>", "<optional query3>"]
}
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/test_image_curator_helpers.py`:

```python
from pathlib import Path

from kelp_teaser.agents.image_curator import (
    ImageQueries,
    curate_image,
)
from kelp_teaser.schemas.plan import ComponentKind, SectionPlan
from kelp_teaser.schemas.slide import HeroImage
from kelp_teaser.tools.image_search import PexelsCandidate
from tests.fixtures.stub_llm import patch_llm


def _section() -> SectionPlan:
    return SectionPlan(
        kind=ComponentKind.hero_image,
        image_brief="pharmaceutical reactor vessel interior",
        data_hooks=[],
    )


def test_curate_image_returns_none_when_no_candidates(monkeypatch, tmp_path):
    patch_llm(monkeypatch, json_responses=[
        ImageQueries(queries=["pharma reactor", "lab equipment"]),
    ])
    monkeypatch.setattr(
        "kelp_teaser.agents.image_curator.image_search.search_pexels",
        lambda q, per_page=5: [],
    )
    result = curate_image(_section(), sector="Pharma", out_dir=tmp_path)
    assert result is None


def test_curate_image_downloads_first_candidate(monkeypatch, tmp_path):
    candidates = [
        PexelsCandidate(photo_id=42, src_large="https://images.pexels.com/x.jpg",
                        photographer="Jane", photographer_url="https://pexels.com/jane",
                        alt="reactor"),
    ]
    patch_llm(monkeypatch, json_responses=[
        ImageQueries(queries=["pharma reactor"]),
    ])
    monkeypatch.setattr(
        "kelp_teaser.agents.image_curator.image_search.search_pexels",
        lambda q, per_page=5: candidates,
    )
    dl_calls = []
    def fake_download(url, dest):
        dl_calls.append((url, dest))
        Path(dest).write_bytes(b"fake-png")
        return True
    monkeypatch.setattr(
        "kelp_teaser.agents.image_curator.image_search.download_image",
        fake_download,
    )
    result = curate_image(_section(), sector="Pharma", out_dir=tmp_path)
    assert isinstance(result, HeroImage)
    assert result.source_id == "image:pexels:42"
    assert Path(result.path).exists()
    assert dl_calls[0][0] == "https://images.pexels.com/x.jpg"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_image_curator_helpers.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `agents/image_curator.py`**

Create `src/kelp_teaser/agents/image_curator.py`:

```python
"""ImageCurator: Flash generates Pexels queries; we download the top candidate.

A future v3 enhancement is a Flash-vision filter on the downloaded image to reject
logos/text/people-in-suits. Phase B keeps it simple: take the first candidate.
"""
from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.schemas.plan import SectionPlan
from kelp_teaser.schemas.slide import HeroImage
from kelp_teaser.tools import image_search, llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)


class ImageQueries(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=4)


def curate_image(section: SectionPlan, *, sector: str, out_dir: Path) -> HeroImage | None:
    if not section.image_brief:
        return None

    prompt = load_prompt("image_curator").render(
        image_brief=section.image_brief, sector=sector,
    )
    try:
        plan = llm.complete_json(MODEL_FAST, prompt, ImageQueries)
    except Exception as e:  # noqa: BLE001
        log.error("ImageCurator query gen failed: %s", e)
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    for query in plan.queries:
        candidates = image_search.search_pexels(query, per_page=3)
        for candidate in candidates:
            if not candidate.src_large:
                continue
            dest = out_dir / f"pexels_{candidate.photo_id}.jpg"
            if image_search.download_image(candidate.src_large, dest):
                return HeroImage(
                    path=str(dest),
                    alt_text=candidate.alt or section.image_brief,
                    source_id=f"image:pexels:{candidate.photo_id}",
                )
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_image_curator_helpers.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/agents/image_curator.py prompts/image_curator.md \
        tests/unit/test_image_curator_helpers.py
git commit -m "feat(agents): ImageCurator (Flash + Pexels) returns a downloaded HeroImage"
```

---

## Task 11: Composer agent + prompt

**Files:**
- Create: `src/kelp_teaser/agents/composer.py`
- Modify: `prompts/composer.md`
- Create: `tests/unit/test_composer_helpers.py`

- [ ] **Step 1: Write the prompt**

Overwrite `prompts/composer.md` with:

```markdown
You compose ONE slide of an M&A blind teaser. Output is a `ComposedSlide`.

## Rules

1. The deck is BLIND: refer to the company as "{{ codename }}". NEVER use the real name.
2. Every bullet, metric, and chart value MUST carry a `source_id` from the supplied source list.
3. Bullets ≤20 words. Metric values are short (e.g. "₹450 Cr", "22%", "600+"). Labels ≤4 words.
4. Use ONLY the facts in the source material. If a section's data isn't supported, return that section with empty bullets/metrics rather than inventing.
5. Don't write marketing prose — write investment facts.

## Inputs

- Slide index: {{ slide_index }}
- Slide title: {{ slide_title }}
- Codename: {{ codename }}
- Section plans for this slide:
{{ section_plans_json }}

- Source material (each source_id must appear verbatim in the relevant Fact's source_id field):
{{ source_context }}

## Response format

Respond with strictly valid JSON matching the `ComposedSlide` schema (see schema hint appended by the runtime).
The `index` field MUST equal {{ slide_index }}.
The `title` field MUST equal "{{ slide_title }}" verbatim.
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/test_composer_helpers.py`:

```python
from pathlib import Path

from kelp_teaser.agents.composer import build_source_context, compose_slide
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.schemas.plan import (
    ChartKind,
    ChartSpecSkeleton,
    ComponentKind,
    SectionPlan,
    SlidePlan,
)
from kelp_teaser.schemas.slide import (
    Bullet,
    ComposedSection,
    ComposedSlide,
    MetricTile,
)
from tests.fixtures.stub_llm import patch_llm


def test_build_source_context_includes_doc_text_and_snippet_summary():
    docs = [IngestedDoc(source_id="doc:x.md", filename="x.md",
                        text="Revenue ₹450 Cr.")]
    snippets = [WebSnippet(source_id="web:tavily:https://x.com",
                           url="https://x.com", summary="600+ customers.")]
    ctx = build_source_context(docs, snippets)
    assert "doc:x.md" in ctx
    assert "Revenue ₹450 Cr" in ctx
    assert "web:tavily:https://x.com" in ctx
    assert "600+ customers" in ctx


def test_compose_slide_returns_composed_slide(monkeypatch, tmp_path):
    docs = [IngestedDoc(source_id="doc:x.md", filename="x.md",
                        text="Revenue ₹450 Cr. 600+ customers.")]
    composed = ComposedSlide(index=0, title="Business Profile", sections=[
        ComposedSection(
            kind=ComponentKind.bullet_list,
            bullets=[
                Bullet(text="Mid-cap tech player", source_id="doc:x.md"),
                Bullet(text="600+ active customers", source_id="doc:x.md"),
            ],
        ),
    ])
    patch_llm(monkeypatch, json_responses=[composed])

    slide_plan = SlidePlan(title="Business Profile", sections=[
        SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["customer_count"]),
    ])

    out = compose_slide(
        slide_index=0, slide_plan=slide_plan, codename="Project Halo",
        docs=docs, web_snippets=[],
        sector="SaaS", out_dir=tmp_path,
    )
    assert out.title == "Business Profile"
    assert out.sections[0].bullets[0].text.startswith("Mid-cap")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_composer_helpers.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `agents/composer.py`**

Create `src/kelp_teaser/agents/composer.py`:

```python
"""Composer: Pro call per slide. Writes the ComposedSlide for one SlidePlan.

Side calls: ChartDesigner for chart sections; ImageCurator for hero_image sections.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from kelp_teaser.agents import chart_designer, image_curator
from kelp_teaser.config import MODEL_SMART
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.schemas.plan import ComponentKind, SlidePlan
from kelp_teaser.schemas.slide import ComposedSection, ComposedSlide
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)


def build_source_context(docs: list[IngestedDoc],
                          snippets: list[WebSnippet]) -> str:
    parts: list[str] = []
    for d in docs:
        parts.append(f"### {d.source_id}\n{d.text.strip()}")
    for s in snippets:
        parts.append(f"### {s.source_id} (from {s.url})\n{s.summary.strip()}")
    return "\n\n".join(parts)


def compose_slide(
    *,
    slide_index: int,
    slide_plan: SlidePlan,
    codename: str,
    docs: list[IngestedDoc],
    web_snippets: list[WebSnippet],
    sector: str,
    out_dir: Path,
) -> ComposedSlide:
    source_context = build_source_context(docs, web_snippets)
    section_plans_json = json.dumps(
        [s.model_dump(mode="json") for s in slide_plan.sections],
        indent=2,
    )
    prompt = load_prompt("composer").render(
        slide_index=slide_index,
        slide_title=slide_plan.title,
        codename=codename,
        section_plans_json=section_plans_json,
        source_context=source_context,
    )
    composed: ComposedSlide = llm.complete_json(MODEL_SMART, prompt, ComposedSlide)

    composed = _attach_charts_and_images(
        composed=composed, slide_plan=slide_plan,
        source_context=source_context, sector=sector, out_dir=out_dir,
    )
    return composed


def _attach_charts_and_images(
    *,
    composed: ComposedSlide,
    slide_plan: SlidePlan,
    source_context: str,
    sector: str,
    out_dir: Path,
) -> ComposedSlide:
    """Pair each ComposedSection with its SectionPlan and run the side agents."""
    new_sections: list[ComposedSection] = []
    paired = list(zip(slide_plan.sections, composed.sections))
    for plan_sec, composed_sec in paired:
        if plan_sec.kind == ComponentKind.chart and composed_sec.chart is None:
            try:
                chart = chart_designer.design_chart(
                    plan_sec, source_context=source_context,
                )
                composed_sec = composed_sec.model_copy(update={"chart": chart})
            except Exception as e:  # noqa: BLE001
                log.error("ChartDesigner failed for slide %s: %s",
                          composed.index, e)
        elif plan_sec.kind == ComponentKind.hero_image and composed_sec.image is None:
            try:
                img = image_curator.curate_image(
                    plan_sec, sector=sector,
                    out_dir=out_dir / "images",
                )
                if img is not None:
                    composed_sec = composed_sec.model_copy(update={"image": img})
            except Exception as e:  # noqa: BLE001
                log.error("ImageCurator failed for slide %s: %s",
                          composed.index, e)
        new_sections.append(composed_sec)
    return composed.model_copy(update={"sections": new_sections})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_composer_helpers.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/agents/composer.py prompts/composer.md \
        tests/unit/test_composer_helpers.py
git commit -m "feat(agents): Composer (Pro) writes ComposedSlide; pairs ChartDesigner + ImageCurator"
```

---

## Task 12: Anonymizer agent + prompt

**Files:**
- Create: `src/kelp_teaser/agents/anonymizer.py`
- Modify: `prompts/anonymizer.md`
- Create: `tests/unit/test_anonymizer.py`

- [ ] **Step 1: Write the prompt**

Overwrite `prompts/anonymizer.md` with:

```markdown
You scrub identifying information from one bullet/metric of a blind teaser.

## Goal

Rewrite the text so the company is unidentifiable while preserving every numeric and qualitative fact.

## Rules

1. Replace any token containing the real name "{{ real_name }}" (case-insensitive) with "{{ codename }}".
2. Generalize specific addresses to a region (e.g. "Pune" → "western India"; "123 Mumbai Industrial Estate" → "an Indian industrial cluster").
3. Replace exact founding years with ranges (e.g. "founded in 1987" → "founded over 35 years ago").
4. Replace founder names with "the founding team".
5. Keep all numbers, percentages, and currency amounts EXACTLY.

## Input

{{ original_text }}

## Response format

Respond with valid JSON:
{
  "replacement": "<rewritten text or the original if no change needed>"
}
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/test_anonymizer.py`:

```python
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
    # First bullet contains the name → 1 LLM call. Second is clean → no call.
    patch_llm(monkeypatch, json_responses=[
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
    # Log captures the substitution
    assert len(result["anonymization_log"]) == 1
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_anonymizer.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `agents/anonymizer.py`**

Create `src/kelp_teaser/agents/anonymizer.py`:

```python
"""Anonymizer: Flash pass that scrubs identifying tokens from each bullet/metric.

Only calls Flash for items that *might* leak — anything containing the real company
name token (case-insensitive). Other text is passed through to save tokens.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.critic import Substitution
from kelp_teaser.schemas.slide import (
    Bullet,
    ComposedSection,
    ComposedSlide,
    MetricTile,
)
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)


class _Replacement(BaseModel):
    replacement: str


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    real_name = state.company_name
    codename = state.plan.codename if state.plan else "Project Blind"
    log_entries: list[Substitution] = []
    new_slides: dict[int, ComposedSlide] = {}

    for idx, slide in state.composed_slides.items():
        new_sections: list[ComposedSection] = []
        for section in slide.sections:
            new_section = section.model_copy(deep=True)
            new_section.bullets = [
                _scrub_bullet(b, real_name, codename, idx, log_entries)
                for b in section.bullets
            ]
            new_section.metrics = [
                _scrub_metric(m, real_name, codename, idx, log_entries)
                for m in section.metrics
            ]
            new_sections.append(new_section)
        new_slides[idx] = slide.model_copy(update={"sections": new_sections})

    if trace_writer is not None:
        trace_writer.write_step("anonymizer", {
            "substitution_count": len(log_entries),
            "substitutions": [s.model_dump() for s in log_entries],
        })

    return {"composed_slides": new_slides, "anonymization_log": log_entries}


def _scrub_text(text: str, real_name: str, codename: str) -> str:
    if real_name.lower() not in text.lower():
        return text
    prompt = load_prompt("anonymizer").render(
        real_name=real_name, codename=codename, original_text=text,
    )
    try:
        out = llm.complete_json(MODEL_FAST, prompt, _Replacement)
        return out.replacement or text
    except Exception as e:  # noqa: BLE001
        log.error("Anonymizer call failed: %s", e)
        # Fallback: case-insensitive literal swap of the company name.
        return _literal_swap(text, real_name, codename)


def _literal_swap(text: str, real_name: str, codename: str) -> str:
    # Case-insensitive replacement of whole/partial occurrences.
    out = []
    cursor = 0
    lower = text.lower()
    needle = real_name.lower()
    while cursor < len(text):
        hit = lower.find(needle, cursor)
        if hit == -1:
            out.append(text[cursor:])
            break
        out.append(text[cursor:hit])
        out.append(codename)
        cursor = hit + len(needle)
    return "".join(out)


def _scrub_bullet(b: Bullet, real_name: str, codename: str,
                  slide_idx: int, log_entries: list[Substitution]) -> Bullet:
    new_text = _scrub_text(b.text, real_name, codename)
    if new_text != b.text:
        log_entries.append(Substitution(original=b.text, replacement=new_text,
                                        slide_index=slide_idx,
                                        reason="bullet leaked real name"))
        return b.model_copy(update={"text": new_text})
    return b


def _scrub_metric(m: MetricTile, real_name: str, codename: str,
                  slide_idx: int, log_entries: list[Substitution]) -> MetricTile:
    new_label = _scrub_text(m.label, real_name, codename)
    new_subtext = _scrub_text(m.subtext, real_name, codename) if m.subtext else ""
    if new_label != m.label or new_subtext != m.subtext:
        log_entries.append(Substitution(
            original=f"{m.label} | {m.subtext}",
            replacement=f"{new_label} | {new_subtext}",
            slide_index=slide_idx,
            reason="metric label/subtext leaked real name",
        ))
        return m.model_copy(update={"label": new_label, "subtext": new_subtext})
    return m
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_anonymizer.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/agents/anonymizer.py prompts/anonymizer.md \
        tests/unit/test_anonymizer.py
git commit -m "feat(agents): Anonymizer (Flash, selective) scrubs real-name tokens with literal-swap fallback"
```

---

## Task 13: Critic agent + prompt

**Files:**
- Create: `src/kelp_teaser/agents/critic.py`
- Modify: `prompts/critic.md`
- Create: `tests/unit/test_critic.py`

- [ ] **Step 1: Write the prompt**

Overwrite `prompts/critic.md` with:

```markdown
You are the QA critic for a blind M&A teaser deck. Review the composed slides and report issues.

## Inputs

- Codename: {{ codename }}
- Original company name (must NOT appear in the deck): {{ real_name }}
- Sector: {{ sector }}
- Composed slides (JSON):
{{ composed_slides_json }}
- Available source IDs (each claim's source_id must be in this list):
{{ source_ids_json }}

## Checks (LLM judgment portion)

For each slide, evaluate:
- **Sector fit:** do the chosen sections suit the sector?
- **Length discipline:** any bullet >20 words?
- **Anonymization completeness:** any residual leakage beyond simple name replacement (e.g. unique product names, exact addresses, founder names)?

Note: source-ID existence and exact-string anonymization checks are done deterministically in code — focus on judgmental issues.

## Severity

- `info`: minor stylistic remark
- `warning`: should be improved
- `blocking`: this would embarrass the deck

## Response format

Respond with strictly valid JSON matching the `CriticReport` schema (see schema hint appended by the runtime). If no issues, return `{"issues": []}`.
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/test_critic.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_critic.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `agents/critic.py`**

Create `src/kelp_teaser/agents/critic.py`:

```python
"""Critic: deterministic checks + a Flash judgment pass. Single pass, no loop."""
from __future__ import annotations

import json
import logging

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.critic import CriticIssue, CriticReport, CriticSeverity
from kelp_teaser.schemas.slide import ComposedSlide
from kelp_teaser.tools import llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)

MAX_BULLET_WORDS = 20


def deterministic_checks(
    composed_slides: dict[int, ComposedSlide],
    *,
    valid_source_ids: set[str],
    real_name: str,
) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    real_lower = real_name.lower()

    for idx, slide in composed_slides.items():
        for section in slide.sections:
            for b in section.bullets:
                if b.source_id not in valid_source_ids:
                    issues.append(CriticIssue(
                        slide_index=idx, severity=CriticSeverity.blocking,
                        category="source_validity",
                        detail=f"bullet source_id {b.source_id!r} not found in inputs",
                    ))
                if len(b.text.split()) > MAX_BULLET_WORDS:
                    issues.append(CriticIssue(
                        slide_index=idx, severity=CriticSeverity.warning,
                        category="length_discipline",
                        detail=f"bullet >{MAX_BULLET_WORDS} words: {b.text[:60]!r}",
                    ))
                if real_lower in b.text.lower():
                    issues.append(CriticIssue(
                        slide_index=idx, severity=CriticSeverity.blocking,
                        category="anonymization_leak",
                        detail=f"bullet contains real name: {b.text[:60]!r}",
                    ))
            for m in section.metrics:
                if m.source_id not in valid_source_ids:
                    issues.append(CriticIssue(
                        slide_index=idx, severity=CriticSeverity.blocking,
                        category="source_validity",
                        detail=f"metric source_id {m.source_id!r} not found in inputs",
                    ))
                if real_lower in m.label.lower() or real_lower in m.subtext.lower():
                    issues.append(CriticIssue(
                        slide_index=idx, severity=CriticSeverity.blocking,
                        category="anonymization_leak",
                        detail=f"metric contains real name: {m.label!r}",
                    ))
            if section.chart is not None and section.chart.source_id not in valid_source_ids:
                issues.append(CriticIssue(
                    slide_index=idx, severity=CriticSeverity.warning,
                    category="source_validity",
                    detail=f"chart source_id {section.chart.source_id!r} not found",
                ))

    return issues


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    valid_source_ids = (
        {d.source_id for d in state.docs}
        | {s.source_id for s in state.web_snippets}
    )
    real_name = state.company_name
    codename = state.plan.codename if state.plan else "Project Blind"

    deterministic = deterministic_checks(
        state.composed_slides,
        valid_source_ids=valid_source_ids,
        real_name=real_name,
    )

    composed_json = json.dumps(
        {i: s.model_dump(mode="json") for i, s in state.composed_slides.items()},
        indent=2,
    )
    prompt = load_prompt("critic").render(
        codename=codename,
        real_name=real_name,
        sector=(state.sector.value if state.sector else "Other"),
        composed_slides_json=composed_json,
        source_ids_json=json.dumps(sorted(valid_source_ids)),
    )
    try:
        judgmental = llm.complete_json(MODEL_FAST, prompt, CriticReport).issues
    except Exception as e:  # noqa: BLE001
        log.error("Critic LLM judgment failed: %s", e)
        judgmental = []

    report = CriticReport(issues=deterministic + judgmental)

    if trace_writer is not None:
        trace_writer.write_step("critic", {
            "deterministic_issues": len(deterministic),
            "judgmental_issues": len(judgmental),
            "blocking_count": sum(1 for i in report.issues
                                  if i.severity == CriticSeverity.blocking),
            "report": report.model_dump(),
        })

    return {"critic_report": report}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_critic.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/agents/critic.py prompts/critic.md tests/unit/test_critic.py
git commit -m "feat(agents): Critic with deterministic + Flash-judgment checks (single pass)"
```

---

## Task 14: CitationTracker agent (no LLM)

**Files:**
- Create: `src/kelp_teaser/agents/citation_tracker.py`
- Create: `tests/unit/test_citation_tracker.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_citation_tracker.py`:

```python
from pathlib import Path

from kelp_teaser.agents.citation_tracker import run as run_tracker
from kelp_teaser.graph.state import GraphState
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.schemas.plan import ComponentKind
from kelp_teaser.schemas.slide import (
    Bullet, ComposedSection, ComposedSlide, MetricTile,
)


def test_citation_tracker_builds_one_row_per_claim():
    docs = [IngestedDoc(source_id="doc:x.md", filename="x.md",
                        text="Revenue ₹450 Cr in FY24.")]
    snippets = [WebSnippet(source_id="web:tavily:https://acme.com",
                           url="https://acme.com",
                           summary="600+ active customers.")]
    slide0 = ComposedSlide(index=0, title="Slide 1", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="600+ active customers globally", source_id="web:tavily:https://acme.com"),
        ]),
        ComposedSection(kind=ComponentKind.metric_tile, metrics=[
            MetricTile(value="₹450 Cr", label="Revenue FY24", source_id="doc:x.md"),
        ]),
    ])
    state = GraphState(company_name="Acme", input_path=Path("."), run_id="r1",
                       docs=docs, web_snippets=snippets,
                       composed_slides={0: slide0})

    result = run_tracker(state)
    table = result["citation_table"]
    assert len(table.rows) == 2
    claims = {row.claim for row in table.rows}
    assert "600+ active customers globally" in claims
    sources = {row.source_id for row in table.rows}
    assert "doc:x.md" in sources
    assert "web:tavily:https://acme.com" in sources


def test_citation_tracker_includes_chart_source():
    from kelp_teaser.schemas.plan import ChartKind
    from kelp_teaser.schemas.slide import ChartSeries, ChartSpec
    slide = ComposedSlide(index=0, title="t", sections=[
        ComposedSection(kind=ComponentKind.chart, chart=ChartSpec(
            chart_kind=ChartKind.revenue_growth_bar,
            title="Revenue",
            categories=["FY22", "FY23"],
            series=[ChartSeries(name="R", values=[1, 2])],
            source_id="doc:x.md",
        )),
    ])
    state = GraphState(company_name="Acme", input_path=Path("."), run_id="r1",
                       docs=[IngestedDoc(source_id="doc:x.md",
                                         filename="x.md", text="t")],
                       composed_slides={0: slide})
    table = run_tracker(state)["citation_table"]
    assert any(r.source_id == "doc:x.md" and "Revenue" in r.claim
               for r in table.rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_citation_tracker.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `agents/citation_tracker.py`**

Create `src/kelp_teaser/agents/citation_tracker.py`:

```python
"""CitationTracker: pure aggregation; produces the structured citation table."""
from __future__ import annotations

from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.citations import CitationRow, CitationTable
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet


def _verbatim_quote_for(source_id: str, docs: list[IngestedDoc],
                         snippets: list[WebSnippet], claim: str) -> str:
    """Best-effort: pull a short verbatim from the source matching the claim."""
    for d in docs:
        if d.source_id == source_id:
            return _excerpt_around(d.text, claim)
    for s in snippets:
        if s.source_id == source_id:
            return _excerpt_around(s.summary, claim)
    return ""


def _excerpt_around(text: str, claim: str, window: int = 140) -> str:
    if not text:
        return ""
    needle = claim.split()[0] if claim else ""
    idx = text.lower().find(needle.lower()) if needle else -1
    if idx == -1:
        return text[:window]
    start = max(0, idx - window // 4)
    return text[start: start + window].strip()


def run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict:
    rows: list[CitationRow] = []
    for idx, slide in sorted(state.composed_slides.items()):
        for section in slide.sections:
            for b in section.bullets:
                rows.append(CitationRow(
                    slide_index=idx, claim=b.text, source_id=b.source_id,
                    verbatim_quote=_verbatim_quote_for(b.source_id, state.docs,
                                                       state.web_snippets, b.text),
                    confidence="High",
                ))
            for m in section.metrics:
                claim = f"{m.label}: {m.value}" + (f" ({m.subtext})" if m.subtext else "")
                rows.append(CitationRow(
                    slide_index=idx, claim=claim, source_id=m.source_id,
                    verbatim_quote=_verbatim_quote_for(m.source_id, state.docs,
                                                       state.web_snippets, m.value),
                    confidence="High",
                ))
            if section.chart is not None:
                rows.append(CitationRow(
                    slide_index=idx,
                    claim=f"Chart: {section.chart.title or section.chart.chart_kind.value}",
                    source_id=section.chart.source_id,
                    verbatim_quote=_verbatim_quote_for(section.chart.source_id,
                                                       state.docs, state.web_snippets,
                                                       section.chart.title or ""),
                    confidence="Medium",
                ))
            if section.image is not None:
                rows.append(CitationRow(
                    slide_index=idx,
                    claim=f"Image: {section.image.alt_text or 'stock photo'}",
                    source_id=section.image.source_id,
                    verbatim_quote="Pexels stock photo (CC0 license)",
                    confidence="High",
                ))

    table = CitationTable(rows=rows)
    if trace_writer is not None:
        trace_writer.write_step("citation_tracker", {"row_count": len(rows)})
    return {"citation_table": table}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_citation_tracker.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/agents/citation_tracker.py tests/unit/test_citation_tracker.py
git commit -m "feat(agents): CitationTracker aggregates per-claim CitationRows"
```

---

## Task 15: Wrap Ingestor/Researcher/SectorClassifier/Planner/Anonymizer/Critic/CitationTracker as LangGraph nodes that update state

This task ensures each agent's `run()` is callable from LangGraph. LangGraph nodes accept a state and return a dict to merge. Our agents already match that signature. This task adds a tiny adapter that injects a TraceWriter from a config keyword.

**Files:**
- Modify each agent file to ensure `run(state, *, trace_writer=None) -> dict` signature is consistent (most already are; verify).
- Create: `src/kelp_teaser/graph/nodes.py` with thin wrappers that bind a shared TraceWriter.
- Create: `tests/unit/test_graph_nodes.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_graph_nodes.py`:

```python
from pathlib import Path

from kelp_teaser.graph.nodes import bind_node
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter


def test_bind_node_injects_trace_writer():
    captured = {}

    def fake_agent(state, *, trace_writer=None):
        captured["trace_writer"] = trace_writer
        return {"company_name": state.company_name}

    writer = TraceWriter(run_dir=None)
    node = bind_node(fake_agent, trace_writer=writer)
    out = node(GraphState(company_name="Acme", input_path=Path("."), run_id="r1"))
    assert captured["trace_writer"] is writer
    assert out == {"company_name": "Acme"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_graph_nodes.py -v`
Expected: ImportError on `kelp_teaser.graph.nodes`.

- [ ] **Step 3: Implement `graph/nodes.py`**

Create `src/kelp_teaser/graph/nodes.py`:

```python
"""Thin LangGraph node adapters: bind a TraceWriter to each agent's run()."""
from __future__ import annotations

from typing import Callable

from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter

AgentFn = Callable[..., dict]


def bind_node(agent_run: AgentFn, *, trace_writer: TraceWriter | None) -> Callable[[GraphState], dict]:
    def node(state: GraphState) -> dict:
        return agent_run(state, trace_writer=trace_writer)
    return node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_graph_nodes.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/graph/nodes.py tests/unit/test_graph_nodes.py
git commit -m "feat(graph): bind_node adapter that injects TraceWriter into agent run()"
```

---

## Task 16: Build the LangGraph (sequential + parallel Composer fan-out)

**Files:**
- Create: `src/kelp_teaser/graph/build_graph.py`
- Create: `tests/unit/test_build_graph.py`

The Composer fans out per slide via LangGraph `Send`. Each Composer instance receives a *projection* of state plus its assigned slide_index. The fan-in reducer merges `composed_slides` dicts.

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_build_graph.py`:

```python
from pathlib import Path

from kelp_teaser.graph.build_graph import build_graph
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.critic import CriticReport
from kelp_teaser.schemas.facts import IngestedDoc, WebSnippet
from kelp_teaser.schemas.plan import (
    ChartKind, ChartSpecSkeleton, ComponentKind, DeckPlan, Sector,
    SectionPlan, SlidePlan,
)
from kelp_teaser.schemas.slide import (
    Bullet, ComposedSection, ComposedSlide,
)
from tests.fixtures.stub_llm import patch_llm


def _bullet_slide(idx: int, codename: str = "Project Halo") -> ComposedSlide:
    return ComposedSlide(index=idx, title=f"Slide {idx + 1}", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text=f"{codename} fact {idx}", source_id="doc:Ksolves-OnePager.md"),
        ]),
    ])


def test_graph_runs_end_to_end_with_stubbed_llm(monkeypatch, tmp_path):
    # Stub web_search to nothing (no Researcher LLM calls needed)
    monkeypatch.setattr("kelp_teaser.agents.researcher.web_search.search",
                        lambda query, max_results=5: [])

    plan = DeckPlan(codename="Project Halo", slides=[
        SlidePlan(title=f"Slide {i + 1}", sections=[
            SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["x"]),
        ]) for i in range(3)
    ])
    patch_llm(monkeypatch, json_responses=[
        # SectorClassifier
        {"sector": "SaaS", "sub_sector": "DevOps", "confidence": 0.9},
        # Planner
        plan,
        # 3 Composer calls
        _bullet_slide(0), _bullet_slide(1), _bullet_slide(2),
        # Critic
        CriticReport(issues=[]),
    ])

    # Prepare an input folder
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "Ksolves-OnePager.md").write_text("Mid-cap. Revenue ₹450 Cr. 600+ customers.")

    state = GraphState(company_name="Ksolves", input_path=input_dir, run_id="rtest")
    graph = build_graph(trace_writer=TraceWriter(run_dir=None))
    final = graph.invoke(state)

    # final is a dict-like state. Pydantic re-validates via GraphState.
    final_state = GraphState.model_validate(final)
    assert final_state.plan is not None
    assert final_state.plan.codename == "Project Halo"
    assert len(final_state.composed_slides) == 3
    assert final_state.critic_report is not None
    assert final_state.citation_table is not None
    assert len(final_state.citation_table.rows) >= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_build_graph.py -v`
Expected: ImportError on `kelp_teaser.graph.build_graph`.

- [ ] **Step 3: Implement `graph/build_graph.py`**

Create `src/kelp_teaser/graph/build_graph.py`:

```python
"""LangGraph topology for the v2 teaser pipeline.

Sequential: Ingestor → Researcher → SectorClassifier → Planner
Parallel fan-out (Send): 3 Composer instances, one per slide
Sequential: Anonymizer → Critic → CitationTracker → END
"""
from __future__ import annotations

import operator
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from kelp_teaser.agents import (
    anonymizer,
    citation_tracker,
    composer as composer_agent,
    critic,
    ingestor,
    planner,
    researcher,
    sector_classifier,
)
from kelp_teaser.graph.nodes import bind_node
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.schemas.slide import ComposedSlide


class _GraphDict(TypedDict, total=False):
    """LangGraph requires a TypedDict-shaped state with reducers per key.

    Most fields use the default replace-on-update. `composed_slides` uses dict-merge
    to support parallel fan-in.
    """
    company_name: str
    input_path: Path
    run_id: str
    docs: list
    web_snippets: list
    planner_brief: str
    sector: object
    sector_confidence: float | None
    sub_sector: str
    plan: object
    composed_slides: Annotated[dict[int, ComposedSlide], operator.or_]
    anonymization_log: list
    critic_report: object
    citation_table: object
    pptx_path: Path | None
    citations_path: Path | None
    trace_path: Path | None


def build_graph(*, trace_writer: TraceWriter | None = None,
                run_dir: Path | None = None):
    sg: StateGraph = StateGraph(_GraphDict)

    sg.add_node("ingestor", bind_node(ingestor.run, trace_writer=trace_writer))
    sg.add_node("researcher", bind_node(researcher.run, trace_writer=trace_writer))
    sg.add_node("sector_classifier",
                bind_node(sector_classifier.run, trace_writer=trace_writer))
    sg.add_node("planner", bind_node(planner.run, trace_writer=trace_writer))
    sg.add_node("composer", _composer_node_factory(trace_writer, run_dir))
    sg.add_node("anonymizer", bind_node(anonymizer.run, trace_writer=trace_writer))
    sg.add_node("critic", bind_node(critic.run, trace_writer=trace_writer))
    sg.add_node("citation_tracker",
                bind_node(citation_tracker.run, trace_writer=trace_writer))

    sg.add_edge(START, "ingestor")
    sg.add_edge("ingestor", "researcher")
    sg.add_edge("researcher", "sector_classifier")
    sg.add_edge("sector_classifier", "planner")
    sg.add_conditional_edges("planner", _fanout_to_composer, ["composer"])
    sg.add_edge("composer", "anonymizer")
    sg.add_edge("anonymizer", "critic")
    sg.add_edge("critic", "citation_tracker")
    sg.add_edge("citation_tracker", END)

    return sg.compile()


def _fanout_to_composer(state) -> list[Send]:
    """Emit one Send per slide in the plan. Each Send carries the full state
    plus a `_slide_index` injected via the partial state payload.
    """
    state_obj = GraphState.model_validate(state)
    if state_obj.plan is None:
        return []
    sends: list[Send] = []
    for idx in range(len(state_obj.plan.slides)):
        sends.append(Send("composer", {**state, "_slide_index": idx}))
    return sends


def _composer_node_factory(trace_writer: TraceWriter | None,
                            run_dir: Path | None):
    """A composer node that runs for ONE slide and returns {composed_slides: {idx: slide}}.

    LangGraph merges the returned dicts via the operator.or_ reducer on composed_slides.
    The `_slide_index` key is injected by `_fanout_to_composer` for each Send.

    `run_dir` is the per-run output folder so intermediate images land in tests'
    tmp_path rather than the repo's real data/outputs/.
    """
    _trace = trace_writer
    _run_dir = run_dir

    def composer_one(state) -> dict:
        idx: int = state.get("_slide_index", 0) if isinstance(state, dict) else 0
        state_obj = GraphState.model_validate({k: v for k, v in state.items()
                                                if k != "_slide_index"})
        if state_obj.plan is None:
            return {}
        slide_plan = state_obj.plan.slides[idx]
        out_dir = (_run_dir / "intermediate") if _run_dir is not None \
            else (Path("data/outputs") / state_obj.run_id / "intermediate")
        composed = composer_agent.compose_slide(
            slide_index=idx,
            slide_plan=slide_plan,
            codename=state_obj.plan.codename,
            docs=state_obj.docs,
            web_snippets=state_obj.web_snippets,
            sector=(state_obj.sector.value if state_obj.sector else "Other"),
            out_dir=out_dir,
        )
        if _trace is not None:
            _trace.write_step(f"composer_{idx}", composed.model_dump())
        return {"composed_slides": {idx: composed}}

    return composer_one
```

`build_graph` signature should be updated to accept `run_dir`:

```python
def build_graph(*, trace_writer: TraceWriter | None = None,
                run_dir: Path | None = None):
    sg: StateGraph = StateGraph(_GraphDict)
    ...
    sg.add_node("composer", _composer_node_factory(trace_writer, run_dir))
    ...
```

And the CLI passes `run_dir` when building:

```python
graph = build_graph(trace_writer=trace, run_dir=run_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_build_graph.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kelp_teaser/graph/build_graph.py tests/unit/test_build_graph.py
git commit -m "feat(graph): LangGraph topology with parallel Composer fan-out via Send"
```

---

## Task 17: CLI entrypoint

**Files:**
- Create: `src/kelp_teaser/cli.py`
- Create: `tests/unit/test_cli_smoke.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_cli_smoke.py`:

```python
from pathlib import Path

from kelp_teaser.cli import run_pipeline
from kelp_teaser.schemas.critic import CriticReport
from kelp_teaser.schemas.plan import (
    ChartKind, ChartSpecSkeleton, ComponentKind, DeckPlan, SectionPlan, SlidePlan,
)
from kelp_teaser.schemas.slide import Bullet, ComposedSection, ComposedSlide
from tests.fixtures.stub_llm import patch_llm


def _bullet_slide(idx: int) -> ComposedSlide:
    return ComposedSlide(index=idx, title=f"Slide {idx + 1}", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text=f"Project Halo fact {idx}",
                   source_id="doc:Ksolves-OnePager.md"),
        ]),
    ])


def test_run_pipeline_writes_pptx_and_citations(monkeypatch, tmp_path):
    monkeypatch.setattr("kelp_teaser.agents.researcher.web_search.search",
                        lambda query, max_results=5: [])

    plan = DeckPlan(codename="Project Halo", slides=[
        SlidePlan(title=f"Slide {i + 1}", sections=[
            SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["x"]),
        ]) for i in range(3)
    ])
    patch_llm(monkeypatch, json_responses=[
        {"sector": "SaaS", "sub_sector": "DevOps", "confidence": 0.9},
        plan,
        _bullet_slide(0), _bullet_slide(1), _bullet_slide(2),
        CriticReport(issues=[]),
    ])

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "Ksolves-OnePager.md").write_text("Mid-cap. ₹450 Cr.")

    out_dir = tmp_path / "outputs"
    result = run_pipeline(
        company_name="Ksolves",
        input_path=input_dir,
        output_root=out_dir,
        run_id="rtest",
    )
    assert result.pptx_path is not None
    assert result.pptx_path.exists()
    assert result.citations_path is not None
    assert result.citations_path.exists()
    assert result.trace_path is not None
    assert result.trace_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_cli_smoke.py -v`
Expected: ImportError on `kelp_teaser.cli`.

- [ ] **Step 3: Implement `cli.py`**

Create `src/kelp_teaser/cli.py`:

```python
"""CLI entrypoint: `kelp-teaser run <input-folder>`.

The `run_pipeline()` function is also called directly from tests.
"""
from __future__ import annotations

import argparse
import logging
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from kelp_teaser.config import DATA_OUTPUTS_DIR
from kelp_teaser.graph.build_graph import build_graph
from kelp_teaser.graph.state import GraphState
from kelp_teaser.graph.trace import TraceWriter
from kelp_teaser.render.citations_doc import render_citations_doc
from kelp_teaser.render.deck import render_deck

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    pptx_path: Path
    citations_path: Path
    trace_path: Path | None


def run_pipeline(
    *,
    company_name: str,
    input_path: Path,
    output_root: Path = DATA_OUTPUTS_DIR,
    run_id: str | None = None,
) -> RunResult:
    rid = run_id or f"{company_name}_{uuid.uuid4().hex[:8]}"
    run_dir = output_root / rid
    run_dir.mkdir(parents=True, exist_ok=True)
    trace = TraceWriter(run_dir=run_dir)

    state = GraphState(
        company_name=company_name,
        input_path=input_path,
        run_id=rid,
    )

    graph = build_graph(trace_writer=trace, run_dir=run_dir)
    final_dict = graph.invoke(state)
    final = GraphState.model_validate(final_dict)

    if not final.composed_slides or not final.plan:
        raise RuntimeError("Pipeline produced no composed slides")

    pptx_path = run_dir / "teaser.pptx"
    render_deck(
        slides=sorted(final.composed_slides.values(), key=lambda s: s.index),
        codename=final.plan.codename,
        out_path=pptx_path,
    )

    citations_path = run_dir / "citations.docx"
    if final.citation_table is not None:
        render_citations_doc(final.citation_table, citations_path)

    trace_path = trace.finalize()

    print(f"Wrote {pptx_path}")
    print(f"Wrote {citations_path}")
    if trace_path:
        print(f"Wrote {trace_path}")

    return RunResult(pptx_path=pptx_path, citations_path=citations_path,
                     trace_path=trace_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kelp-teaser")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="Run the teaser pipeline on a data pack")
    run.add_argument("input_path", type=Path,
                     help="Path to a company folder under data/inputs/")
    run.add_argument("--company", required=False,
                     help="Override company name (defaults to input folder name)")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.cmd == "run":
        input_path: Path = args.input_path
        if not input_path.exists():
            print(f"Input path does not exist: {input_path}", file=sys.stderr)
            return 2
        company = args.company or input_path.name
        result = run_pipeline(company_name=company, input_path=input_path)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_cli_smoke.py -v`
Expected: 1 passed.

- [ ] **Step 5: Smoke the CLI invocation parsing (no real API calls)**

Run: `python -c "from kelp_teaser.cli import main; import sys; sys.exit(main(['--help']))"`
Expected: argparse prints help and exits 0 (or 2 — both fine; we just want no crash).

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/cli.py tests/unit/test_cli_smoke.py
git commit -m "feat(cli): kelp-teaser run <input-folder> end-to-end entrypoint"
```

---

## Task 18: Wire cost-guardrail abort

**Files:**
- Modify: `src/kelp_teaser/cli.py`
- Modify: `src/kelp_teaser/tools/llm.py`
- Modify: `tests/unit/test_llm.py`

The cost-tracker must trigger a hard abort when `total_cost_usd > COST_HARD_ABORT` and a warning at `COST_SOFT_WARNING`. We add a `CostExceeded` exception and a check at the end of every `complete_text` call.

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_llm.py`:

```python
from kelp_teaser.tools.llm import (
    CostExceeded,
    CostTracker,
    GeminiCall,
    check_cost_budget,
)


class TestCostGuardrail:
    def test_check_cost_budget_under_warning_passes(self):
        tracker = CostTracker()
        tracker.record(GeminiCall(model="gemini-2.5-flash",
                                  prompt_tokens=10, output_tokens=5))
        check_cost_budget(tracker, soft_warning=2.00, hard_abort=5.00)

    def test_check_cost_budget_over_abort_raises(self):
        tracker = CostTracker()
        # Force cost > $5 by recording many expensive Pro calls.
        for _ in range(1000):
            tracker.record(GeminiCall(model="gemini-2.5-pro",
                                      prompt_tokens=10_000, output_tokens=10_000))
        with pytest.raises(CostExceeded):
            check_cost_budget(tracker, soft_warning=2.00, hard_abort=5.00)
```

(`pytest` is already imported at the top of the file from earlier tasks.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_llm.py::TestCostGuardrail -v`
Expected: ImportError on `CostExceeded` / `check_cost_budget`.

- [ ] **Step 3: Add guardrail to `tools/llm.py`**

In `src/kelp_teaser/tools/llm.py`, append (or insert near the top after CostTracker):

```python
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
        log.warning("Run cost ${%.2f} exceeded soft warning ${%.2f}",
                    total, soft_warning)
```

- [ ] **Step 4: Wire the check into `complete_text`**

In the same file, replace the `complete_text` function's call-recording block so that after `tracker.record(...)` is called, we also run `check_cost_budget` if `tracker` is not None. Specifically, after the `if tracker is not None:` block in `complete_text`, add:

```python
            if tracker is not None:
                check_cost_budget(
                    tracker,
                    soft_warning=COST_SOFT_WARNING,
                    hard_abort=COST_HARD_ABORT,
                )
```

And add these imports at the top of `llm.py`:

```python
from kelp_teaser.config import (
    GEMINI_API_KEY,
    LLM_MAX_ATTEMPTS,
    COST_SOFT_WARNING,
    COST_HARD_ABORT,
)
```

(Replacing the existing `from kelp_teaser.config import GEMINI_API_KEY, LLM_MAX_ATTEMPTS` line.)

- [ ] **Step 5: Wire a shared tracker through the pipeline**

In `src/kelp_teaser/cli.py`, replace `run_pipeline` to construct a `CostTracker`, pass it (via a module-level global captured by agents) into each agent, and print the cost at the end.

Specifically, since the agents currently call `llm.complete_*` without passing a tracker, the simplest wire-up is to add a module-level `CURRENT_TRACKER` in `tools/llm.py` and use it as the default in `complete_text` / `complete_json` if no `tracker` kwarg is passed:

Modify the bottom of `tools/llm.py`:

```python
# Module-level shared tracker, set by the CLI for the duration of a run.
CURRENT_TRACKER: CostTracker | None = None
```

And modify `complete_text` and `complete_json` signatures so that if `tracker` is None, they fall back to `CURRENT_TRACKER`. Specifically inside `complete_text`, near the top:

```python
    if tracker is None:
        tracker = CURRENT_TRACKER
```

(Repeat the same line inside `complete_json` before it calls `complete_text`, so the cost is recorded on the shared tracker.)

Then in `cli.py`, in `run_pipeline`, set the global before invoking the graph:

```python
    import kelp_teaser.tools.llm as llm_module
    tracker = llm_module.CostTracker()
    llm_module.CURRENT_TRACKER = tracker
    try:
        final_dict = graph.invoke(state)
    finally:
        llm_module.CURRENT_TRACKER = None
    final = GraphState.model_validate(final_dict)

    print(f"Run cost: ${tracker.total_cost_usd:.4f} across {tracker.total_calls} calls")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest -v`
Expected: all previous tests still pass. The new cost-guardrail tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/kelp_teaser/tools/llm.py src/kelp_teaser/cli.py tests/unit/test_llm.py
git commit -m "feat(tools): cost-budget guardrail with CostExceeded; shared tracker via CURRENT_TRACKER"
```

---

## Task 19: Delete v1 scripts

**Files:**
- Delete: `analyze.py`, `check_models.py`, `generate_citations.py`, `ingest.py`, `main.py`, `ppt_engine.py`, `utils.py`, `requirements.txt`, `example_company.md` (only those still at the repo root).

The v2 CLI is wired and tested. The v1 scripts at the repo root are dead code that depends on `examples/` (now moved to `data/inputs/`). Delete them.

- [ ] **Step 1: List what will be deleted**

Run: `ls -1 *.py requirements.txt example_company.md 2>&1`
Expected: shows the 7 .py files, requirements.txt, and `example_company.md`. If any of these are NOT present (because Phase A migration moved them already), skip those.

- [ ] **Step 2: Delete and stage**

```bash
for f in analyze.py check_models.py generate_citations.py ingest.py main.py ppt_engine.py utils.py requirements.txt; do
  if [ -f "$f" ]; then git rm "$f"; fi
done
if [ -f example_company.md ]; then git rm example_company.md; fi
```

- [ ] **Step 3: Confirm no remaining imports of these modules**

Run: `grep -rE "^(from|import) (analyze|ingest|ppt_engine|utils|generate_citations|check_models|main)\b" src/ tests/ || echo "OK no imports"`
Expected: `OK no imports`. If anything matches, those imports must be removed before continuing — the v1 modules are gone.

- [ ] **Step 4: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass (no regression — nothing in v2 imported v1).

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: remove v1 scripts and requirements.txt now that v2 CLI is live"
```

---

## Task 20: Archive remaining v1 root artifacts (if any)

**Files:**
- Move: any remaining `*_ANALYSIS.json` and `*_FULL_CONTEXT.txt` at the repo root → `archive/v1/`
- Move: `examples/Gati-OnePager/` (an orphan folder from v1 runs) if it exists

- [ ] **Step 1: Survey**

```bash
ls *_ANALYSIS.json *_FULL_CONTEXT.txt 2>&1
ls examples/ 2>&1
```

If none exist, this task is a no-op — skip to Step 4 with `--allow-empty`.

- [ ] **Step 2: Archive any that exist**

```bash
mkdir -p archive/v1
shopt -s nullglob
for f in *_ANALYSIS.json *_FULL_CONTEXT.txt; do
  mv "$f" "archive/v1/$f"
done
if [ -d examples ]; then
  mv examples "archive/v1/examples"
fi
shopt -u nullglob
git add -A archive/ examples/ || true
```

- [ ] **Step 3: Confirm clean root**

Run: `ls *_ANALYSIS.json *_FULL_CONTEXT.txt 2>&1; ls examples/ 2>&1`
Expected: all three commands report "No such file or directory" or empty.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: archive remaining v1 root artifacts to archive/v1/" --allow-empty
```

---

## Task 21: Update README for v2

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md` with v2 content**

Overwrite `README.md` with:

```markdown
# Kelp Teaser v2 — Agentic Deal Flow Pipeline

An end-to-end agentic pipeline that converts a company data pack (PDF / Excel / Markdown) into a blind M&A investment teaser deck (.pptx) and a structured citations document (.docx), with every claim mapped back to its source.

Built on **LangGraph** (orchestration), **Google Gemini** (Flash + Pro), **python-pptx** (native chart and shape rendering), and **Pydantic** (strict schemas at every boundary).

## What's new vs. v1

- **Dynamic slide composition.** A Planner agent decides per-company which sections appear in what order and with which visual components. No two decks share a layout.
- **Sector-aware.** A SectorClassifier picks from 9 sectors (Manufacturing, SpecialtyChemicals, D2C, SaaS, Pharma, Logistics, FinancialServices, Consumer, Other) and the Planner adapts.
- **Blind by design.** Real company name never reaches the deck. A codename is assigned at planning time; an Anonymizer pass scrubs residual leaks; a Critic spot-checks.
- **Per-claim citation integrity.** Every bullet, metric, chart value, and image carries a `source_id` enforced by Pydantic. The Citations doc is a 6-column Word table mapping each claim back to its source with a verbatim quote.
- **Bounded cost.** Per-run target is $0.20–$0.40 on Gemini API. Soft warning at $2, hard abort at $5.
- **Full trace.** Every agent's input/output lands in `data/outputs/{company}_{run_id}/intermediate/{NN}_{agent}.json` plus a top-level `trace.json` with cost and timing.

## Installation

```bash
git clone https://github.com/neepun06/AI-ML-GC-RND.git
cd AI-ML-GC-RND
python -m venv venv && source venv/Scripts/activate    # Windows bash; use bin/activate on Linux/macOS
pip install -e ".[dev]"
cp .env.example .env  # fill in GEMINI_API_KEY, TAVILY_API_KEY, LLAMA_CLOUD_API_KEY, PEXELS_API_KEY
```

## Run

```bash
kelp-teaser run data/inputs/Ksolves/
```

Outputs land at `data/outputs/<company>_<run_id>/`:
- `teaser.pptx` — the blind 3-slide deck
- `citations.docx` — per-claim source table
- `trace.json` — cost, timing, and per-step trace
- `intermediate/` — per-agent JSON dumps for debugging

## Architecture

```
Ingestor → Researcher → SectorClassifier → Planner
   → [Composer × 3, parallel via LangGraph Send]
        ↳ ChartDesigner / ImageCurator per section
   → Anonymizer → Critic (single pass) → CitationTracker
   → DeckRenderer + CitationDocRenderer → END
```

See [docs/superpowers/specs/2026-05-16-agentic-teaser-pipeline-design.md](docs/superpowers/specs/2026-05-16-agentic-teaser-pipeline-design.md) for the full design.

## Development

- All source: `src/kelp_teaser/`
- All tests: `pytest -v` (no LLM calls; uses `tests/fixtures/stub_llm.py`)
- All prompts: `prompts/*.md` (Jinja2-templated Markdown; reload at runtime)

## License

Personal portfolio project. Not intended for commercial redistribution.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: replace v1 README with v2 architecture and usage"
```

---

## Task 22: Phase B closeout — full suite green + manual smoke instructions

**Files:** none new

- [ ] **Step 1: Run the entire suite**

Run: `pytest -v`
Expected: every test passes. Count should be approximately Phase A (61) + Phase B new tests. Phase B adds: 2 (llm thread-safety) + 5 (graph_state) + 3 (trace) + 4 (ingestor) + 4 (researcher) + 2 (sector_classifier) + 2 (planner) + 1 (chart_designer) + 2 (image_curator) + 2 (composer) + 2 (anonymizer) + 4 (critic) + 2 (citation_tracker) + 1 (graph_nodes) + 1 (build_graph) + 1 (cli_smoke) + 2 (cost guardrail). That's roughly +40 tests. Total ~100.

- [ ] **Step 2: Verify the package imports cleanly**

Run:
```bash
python -c "
from kelp_teaser.cli import main, run_pipeline
from kelp_teaser.graph.build_graph import build_graph
from kelp_teaser.graph.state import GraphState
from kelp_teaser.agents import (ingestor, researcher, sector_classifier,
                                  planner, composer, chart_designer, image_curator,
                                  anonymizer, critic, citation_tracker)
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 3: Document the live-API smoke test (do NOT run unless API keys are wired)**

The full live-API smoke test that exercises real Gemini + Tavily + Pexels calls is NOT in the pytest suite. Run it manually after wiring `.env`:

```bash
kelp-teaser run data/inputs/Ksolves/
```

Expected:
- Console prints `Wrote data/outputs/Ksolves_<rid>/teaser.pptx`, citations.docx, trace.json
- Final line prints `Run cost: $0.XXXX across N calls`
- Opening the .pptx in PowerPoint shows 3 slides, blind codename in headers, no "Ksolves" anywhere in text
- Opening citations.docx shows a 6-column table with every bullet/metric

Do NOT add this to the automated suite — it makes paid API calls.

- [ ] **Step 4: Commit a close-out marker**

```bash
git commit --allow-empty -m "chore: phase B complete (agents + LangGraph + CLI)"
```

---

## Phase B Acceptance Criteria

By the end of this plan, the engineer should have:

1. `pytest -v` passes (~100 tests) with no live API calls.
2. `kelp-teaser run <input-folder>` produces a `.pptx`, a `.docx`, and a `trace.json` under `data/outputs/<company>_<run_id>/`.
3. Every claim on every slide carries a `source_id` that exists in the inputs, enforced by Pydantic.
4. The real company name never appears in the rendered deck (codename only).
5. Per-run cost is tracked, printed, and aborts at `COST_HARD_ABORT`.
6. The 9 specialized agents are each in their own file, each ≤200 lines.
7. The LangGraph topology is in `src/kelp_teaser/graph/build_graph.py`, with parallel Composer fan-out via `Send`.
8. All 7 prompts in `prompts/*.md` have real content.
9. v1 scripts at the repo root are deleted; `requirements.txt` is gone; v2 README reflects the new architecture.
10. Phase C can begin (live-API smoke tests, real-data tuning, final polish on all 5 companies).
