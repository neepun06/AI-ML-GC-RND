# Phase C — Stage 1: Polish Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address the 5 polish/observability items surfaced by the Phase B final code review so the pipeline is ready for live Gemini runs in Stage 2.

**Architecture:** Five small, independent edits across 4 modules: `agents/critic.py`, `cli.py`, `agents/researcher.py`, `agents/composer.py`, and `render/deck.py`. Each fix ships with a unit test and a single commit. No new files, no architectural change. All tests stay stubbed — no live API calls introduced.

**Tech Stack:** Python 3.11, Pydantic v2, LangGraph, pytest. Existing test harness uses `tests.fixtures.stub_llm.patch_llm()` to monkeypatch `complete_text`/`complete_json`.

**Pre-flight checklist (run once before Task 1):**
- Confirm you are on a clean working tree at the latest `main` (commit `58d28e3` or later).
- Run `pytest -v`. Expect **101 passed**. If not, stop and investigate before proceeding.
- Optional but recommended: create a worktree at `../AI-ML-GC-RND-phase-c` on branch `phase-c-live` per PROMPT.md operating instructions.

---

## Task 1: Critic surfaces LLM judgment failures as a synthetic warning

**Why:** Today, when the Critic's Flash judgment call raises, the `except` branch logs and returns `[]`. The final `CriticReport` then contains only deterministic issues, which a downstream consumer may read as "all clear." We want a visible signal in the report.

**Files:**
- Modify: `src/kelp_teaser/agents/critic.py:98-103`
- Test: `tests/unit/test_critic.py` (append a new test function)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_critic.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_critic.py::test_critic_appends_judgment_unavailable_when_llm_raises -v`
Expected: FAIL — `len(judgment_issues) == 1` is `0`, because today the except branch silently returns `[]`.

- [ ] **Step 3: Modify `agents/critic.py` to emit a synthetic warning on judgment failure**

Replace the `try/except` block at [src/kelp_teaser/agents/critic.py:98-102](src/kelp_teaser/agents/critic.py#L98-L102):

```python
    try:
        judgmental = llm.complete_json(MODEL_FAST, prompt, CriticReport).issues
    except Exception as e:  # noqa: BLE001
        log.error("Critic LLM judgment failed: %s", e)
        judgmental = [
            CriticIssue(
                slide_index=0,
                severity=CriticSeverity.warning,
                category="judgment_unavailable",
                detail=f"Critic LLM judgment call failed: {e}",
                suggested_fix="Inspect logs; re-run the Critic step if needed.",
            )
        ]
```

(The synthetic issue is attached to `slide_index=0` because `CriticIssue.slide_index` is `Field(ge=0)` and the failure is not slide-specific. The category name `judgment_unavailable` matches the wording in the Phase B review notes.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_critic.py -v`
Expected: All tests in the file PASS, including the new one.

- [ ] **Step 5: Confirm full suite still green**

Run: `pytest -v`
Expected: 102 passed (101 + new test).

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/agents/critic.py tests/unit/test_critic.py
git commit -m "$(cat <<'EOF'
fix(critic): surface LLM judgment failures as a synthetic warning

When the Flash judgment call raises, append a CriticIssue with
category="judgment_unavailable" (severity=warning) so the report no
longer reads as "all clear" when the LLM pass actually failed.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: CLI records total cost into the trace

**Why:** `TraceWriter.add_cost()` exists but `run_pipeline()` never calls it. Every `trace.json` reports `total_cost_usd: 0.0` regardless of actual spend, making live-run cost auditing impossible.

**Files:**
- Modify: `src/kelp_teaser/cli.py:76` (insert one line just before `trace.finalize()`)
- Test: `tests/unit/test_cli_smoke.py` (extend the existing smoke test)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_cli_smoke.py`:

```python
def test_run_pipeline_records_cost_in_trace(monkeypatch, tmp_path):
    """trace.json must reflect the real CostTracker total, not 0.0."""
    import json
    import kelp_teaser.tools.llm as llm_module

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

    # Pre-seed the tracker by patching CostTracker construction so the
    # tracker created by run_pipeline starts with a known non-zero cost.
    real_ctor = llm_module.CostTracker

    class SeededTracker(real_ctor):
        def __init__(self):
            super().__init__()
            # Simulate a recorded call worth $0.1234.
            self._record_for_test(0.1234)

        def _record_for_test(self, usd):
            with self._lock:
                self.calls.append({"model": "test", "cost_usd": usd,
                                   "input_tokens": 0, "output_tokens": 0})

    monkeypatch.setattr(llm_module, "CostTracker", SeededTracker)

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "Ksolves-OnePager.md").write_text("Mid-cap. 450 Cr.",
                                                    encoding="utf-8")

    result = run_pipeline(
        company_name="Ksolves", input_path=input_dir,
        output_root=tmp_path / "outputs", run_id="rcost",
    )
    trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
    assert trace["total_cost_usd"] >= 0.1234
```

Note: this test depends on `CostTracker` exposing `_lock`, `calls`, and a `total_cost_usd` property summing `calls[*]["cost_usd"]`. Before running it, open `src/kelp_teaser/tools/llm.py` and confirm that contract. If field names differ (e.g. `cost` instead of `cost_usd`), adjust the test's `_record_for_test` helper to match. **Do not** modify `CostTracker` itself for this task.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_cli_smoke.py::test_run_pipeline_records_cost_in_trace -v`
Expected: FAIL — `trace["total_cost_usd"]` is `0.0` because `add_cost()` is never called.

- [ ] **Step 3: Insert the `add_cost` call in `cli.py`**

In [src/kelp_teaser/cli.py:76](src/kelp_teaser/cli.py#L76), find:

```python
    trace_path = trace.finalize()
```

Replace with:

```python
    trace.add_cost(tracker.total_cost_usd)
    trace_path = trace.finalize()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_cli_smoke.py -v`
Expected: Both smoke tests PASS.

- [ ] **Step 5: Confirm full suite still green**

Run: `pytest -v`
Expected: 103 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/cli.py tests/unit/test_cli_smoke.py
git commit -m "$(cat <<'EOF'
fix(cli): record total run cost into trace.json

Call trace.add_cost(tracker.total_cost_usd) before trace.finalize() so
every live run's trace.json reflects the actual spend instead of 0.0.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Researcher warns when Tavily returns zero hits across all queries

**Why:** When every Tavily query returns 0 hits, the Planner gets a brief built only from the docs. Today nothing is logged. We want a `log.warning` and a trace note so the user sees this in the run output and in `trace.json`.

**Files:**
- Modify: `src/kelp_teaser/agents/researcher.py:44-67`
- Test: `tests/unit/test_researcher_helpers.py` (append a new test)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_researcher_helpers.py`:

```python
def test_researcher_warns_and_traces_when_no_tavily_hits(monkeypatch, caplog):
    """When every Tavily query yields zero hits, log a warning AND record
    a 'web_research_empty' flag in the trace step."""
    import logging
    from kelp_teaser.graph.trace import TraceWriter

    monkeypatch.setattr(
        "kelp_teaser.agents.researcher.web_search.search",
        lambda query, max_results=5: [],
    )
    patch_llm(monkeypatch)

    state = _state()
    writer = TraceWriter(run_dir=None)
    caplog.set_level(logging.WARNING, logger="kelp_teaser.agents.researcher")
    result = run_researcher(state, trace_writer=writer)

    assert result["web_snippets"] == []
    assert any("no Tavily hits" in rec.message.lower() or
               "web_research_empty" in rec.message.lower()
               for rec in caplog.records)
    assert len(writer.steps) == 1
    assert writer.steps[0]["data"].get("web_research_empty") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_researcher_helpers.py::test_researcher_warns_and_traces_when_no_tavily_hits -v`
Expected: FAIL — no warning is logged and the trace step has no `web_research_empty` key.

- [ ] **Step 3: Modify `agents/researcher.py` to warn and trace on empty results**

Replace the `run()` function at [src/kelp_teaser/agents/researcher.py:44-67](src/kelp_teaser/agents/researcher.py#L44-L67):

```python
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

    web_research_empty = len(snippets) == 0
    if web_research_empty:
        log.warning(
            "Researcher: no Tavily hits across any query for %r; "
            "Planner brief will be doc-only.",
            state.company_name,
        )

    if trace_writer is not None:
        trace_writer.write_step("researcher", {
            "snippet_count": len(snippets),
            "brief_chars": len(brief),
            "web_research_empty": web_research_empty,
        })

    return {"web_snippets": snippets, "planner_brief": brief}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_researcher_helpers.py -v`
Expected: All researcher tests PASS, including the new one.

- [ ] **Step 5: Confirm full suite still green**

Run: `pytest -v`
Expected: 104 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/agents/researcher.py tests/unit/test_researcher_helpers.py
git commit -m "$(cat <<'EOF'
feat(researcher): warn and trace when Tavily returns zero hits

If every web search query yields zero hits, log a warning and mark the
trace step with web_research_empty=True so empty-research runs are
visible in trace.json instead of silently producing a doc-only brief.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Renderer asserts slide indices are contiguous 0..N-1

**Why:** `render_deck` sorts by `index`, but if the Planner ever emits `[0, 2, 1]` (skipping 1) or `[0, 0, 1]` (duplicate), the deck would render misordered or with a missing slide and no error. A defensive assertion makes this loud rather than silent.

**Files:**
- Modify: `src/kelp_teaser/render/deck.py:26-37`
- Test: `tests/unit/test_deck_render.py` (append a new test)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_deck_render.py`:

```python
import pytest

from kelp_teaser.schemas.plan import ComponentKind
from kelp_teaser.schemas.slide import Bullet, ComposedSection, ComposedSlide


def _bullet(idx: int) -> ComposedSlide:
    return ComposedSlide(index=idx, title=f"Slide {idx}", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="x", source_id="doc:x.md"),
        ]),
    ])


def test_render_deck_rejects_non_contiguous_indices(tmp_path):
    """If indices are not exactly 0..N-1, render_deck must raise rather
    than silently render a misordered or missing-slide deck."""
    slides = [_bullet(0), _bullet(2), _bullet(3)]  # gap at index 1
    with pytest.raises(AssertionError):
        render_deck(slides=slides, codename="Project Halo",
                    out_path=tmp_path / "teaser.pptx")


def test_render_deck_rejects_duplicate_indices(tmp_path):
    slides = [_bullet(0), _bullet(1), _bullet(1)]
    with pytest.raises(AssertionError):
        render_deck(slides=slides, codename="Project Halo",
                    out_path=tmp_path / "teaser.pptx")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_deck_render.py -v`
Expected: The two new tests FAIL because `render_deck` doesn't currently assert anything about indices.

- [ ] **Step 3: Add the contiguity assertion in `render/deck.py`**

Modify the top of [render_deck](src/kelp_teaser/render/deck.py#L26-L37):

```python
def render_deck(*, slides: list[ComposedSlide], codename: str, out_path: Path) -> Path:
    """Render the deck. Returns the saved path."""
    indices = [s.index for s in slides]
    assert sorted(indices) == list(range(len(slides))), (
        f"Slide indices must be contiguous 0..{len(slides) - 1}, "
        f"got {sorted(indices)}"
    )

    prs = Presentation()
    prs.slide_width = theme.SLIDE_W
    prs.slide_height = theme.SLIDE_H

    for composed in sorted(slides, key=lambda s: s.index):
        _render_slide(prs, composed, codename)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return out_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_deck_render.py -v`
Expected: All deck render tests PASS, including both new ones.

- [ ] **Step 5: Confirm full suite still green**

Run: `pytest -v`
Expected: 106 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kelp_teaser/render/deck.py tests/unit/test_deck_render.py
git commit -m "$(cat <<'EOF'
fix(render): assert slide indices are contiguous 0..N-1

Without this guard, a Planner/Composer bug that emits a duplicate or
gap-containing index list would render a misordered or missing-slide
deck silently. Fail loudly instead.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Composer surfaces missing-chart / missing-image as a state warning

**Why:** ChartDesigner and ImageCurator failures inside the Composer currently log silently. A transient API blip could drop a chart that was central to the slide, and no signal reaches the Critic or the trace. We collect these as `composer_warnings` on the result dict and write them into the trace step, so the Critic and trace surface them.

This task is scoped narrowly: we do NOT add a new Pydantic field to `GraphState` or a new `CriticIssue` category. We just propagate a list out of `compose_slide` and let the existing Composer node log/trace it. The full Critic-visible warning is deferred — PROMPT.md marks this item as "(Optional)".

**Files:**
- Modify: `src/kelp_teaser/agents/composer.py:32-96`
- Test: `tests/unit/test_composer_helpers.py` (append a new test)

- [ ] **Step 1: Read the Composer node wrapper before changing signatures**

The `compose_slide()` return type today is `ComposedSlide`. We will change it to `tuple[ComposedSlide, list[str]]` where the list holds human-readable warning strings.

Before editing, grep for direct callers so we update them in lockstep:

Run: `grep -rn "compose_slide(" src/ tests/`
Expected: At least two callers — the Composer node in `src/kelp_teaser/agents/composer.py` (if wired here) and any test file. Note each call site; you will update each one in Step 3.

If grep shows callers outside `composer.py` and `test_composer_helpers.py` (e.g. in `graph/build_graph.py` or `graph/nodes.py`), open those and update them as part of Step 3.

- [ ] **Step 2: Write the failing test**

Append to `tests/unit/test_composer_helpers.py`:

```python
def test_compose_slide_returns_warning_when_chart_designer_fails(
    monkeypatch, tmp_path,
):
    """If a chart section was planned but ChartDesigner raises, compose_slide
    must surface a 'chart_missing' warning in its second return value
    rather than silently dropping the chart."""
    from kelp_teaser.agents import chart_designer

    def boom(plan_sec, *, source_context):
        raise RuntimeError("simulated ChartDesigner failure")

    monkeypatch.setattr(chart_designer, "design_chart", boom)

    docs = [IngestedDoc(source_id="doc:x.md", filename="x.md",
                        text="Revenue ₹450 Cr.")]
    composed = ComposedSlide(index=0, title="Financials", sections=[
        ComposedSection(
            kind=ComponentKind.chart,
            heading="Revenue",
            bullets=[],
            chart=None,  # Composer LLM left it unfilled
        ),
    ])
    patch_llm(monkeypatch, json_responses=[composed])

    slide_plan = SlidePlan(title="Financials", sections=[
        SectionPlan(
            kind=ComponentKind.chart,
            data_hooks=["revenue_fy24"],
            chart_skeleton=ChartSpecSkeleton(kind=ChartKind.bar_vertical),
        ),
    ])

    out, warnings = compose_slide(
        slide_index=0, slide_plan=slide_plan, codename="Project Halo",
        docs=docs, web_snippets=[],
        sector="SaaS", out_dir=tmp_path,
    )
    assert out.sections[0].chart is None
    assert any("chart_missing" in w for w in warnings)
    assert any("simulated ChartDesigner failure" in w for w in warnings)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_composer_helpers.py::test_compose_slide_returns_warning_when_chart_designer_fails -v`
Expected: FAIL — `compose_slide` returns a `ComposedSlide`, not a tuple. The unpack on `out, warnings = compose_slide(...)` will raise `TypeError: cannot unpack non-iterable ComposedSlide object`.

- [ ] **Step 4: Change `compose_slide` and `_attach_charts_and_images` to return warnings**

Replace [src/kelp_teaser/agents/composer.py:32-96](src/kelp_teaser/agents/composer.py#L32-L96) with:

```python
def compose_slide(
    *,
    slide_index: int,
    slide_plan: SlidePlan,
    codename: str,
    docs: list[IngestedDoc],
    web_snippets: list[WebSnippet],
    sector: str,
    out_dir: Path,
) -> tuple[ComposedSlide, list[str]]:
    """Compose one slide. Returns (composed_slide, warnings).

    Warnings is a list of human-readable strings describing sub-call
    failures (e.g. "chart_missing: ChartDesigner failed for slide 0:
    <reason>"). Empty list on a clean run.
    """
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

    composed, warnings = _attach_charts_and_images(
        composed=composed, slide_plan=slide_plan,
        source_context=source_context, sector=sector, out_dir=out_dir,
    )
    return composed, warnings


def _attach_charts_and_images(
    *,
    composed: ComposedSlide,
    slide_plan: SlidePlan,
    source_context: str,
    sector: str,
    out_dir: Path,
) -> tuple[ComposedSlide, list[str]]:
    """Pair each ComposedSection with its SectionPlan and run the side agents.

    Returns (updated_composed, warnings).
    """
    new_sections: list[ComposedSection] = []
    warnings: list[str] = []
    paired = list(zip(slide_plan.sections, composed.sections))
    for plan_sec, composed_sec in paired:
        if plan_sec.kind == ComponentKind.chart and composed_sec.chart is None:
            try:
                chart = chart_designer.design_chart(
                    plan_sec, source_context=source_context,
                )
                composed_sec = composed_sec.model_copy(update={"chart": chart})
            except Exception as e:  # noqa: BLE001
                msg = (f"chart_missing: ChartDesigner failed for slide "
                       f"{composed.index}: {e}")
                log.error(msg)
                warnings.append(msg)
        elif plan_sec.kind == ComponentKind.hero_image and composed_sec.image is None:
            try:
                img = image_curator.curate_image(
                    plan_sec, sector=sector,
                    out_dir=out_dir / "images",
                )
                if img is not None:
                    composed_sec = composed_sec.model_copy(update={"image": img})
                else:
                    msg = (f"image_missing: ImageCurator returned None for "
                           f"slide {composed.index}")
                    log.warning(msg)
                    warnings.append(msg)
            except Exception as e:  # noqa: BLE001
                msg = (f"image_missing: ImageCurator failed for slide "
                       f"{composed.index}: {e}")
                log.error(msg)
                warnings.append(msg)
        new_sections.append(composed_sec)
    return composed.model_copy(update={"sections": new_sections}), warnings
```

- [ ] **Step 5: Update every other caller of `compose_slide`**

For each call site you noted in Step 1 outside the test you just wrote, update it to unpack the tuple. The expected caller is the Composer node in `agents/composer.py` (or in `graph/build_graph.py` — wherever the `Send`-fan-out invokes it). It should look like:

```python
composed, warnings = compose_slide(...)
# ... return the composed slide; surface warnings via the trace step.
```

Concretely, if the caller currently returns something like:

```python
return {"composed_slides": {slide_index: composed}}
```

Change it to also include warnings in the trace step. If the caller already writes a trace step for `"composer"`, add `"warnings": warnings` to that step's data dict. If not, add:

```python
if trace_writer is not None:
    trace_writer.write_step(f"composer_slide_{slide_index}", {
        "warnings": warnings,
        "warning_count": len(warnings),
    })
```

**Do not** add `warnings` to `GraphState` — it's not needed for downstream agents and would require a Pydantic schema change.

- [ ] **Step 6: Run the failing test to verify it now passes**

Run: `pytest tests/unit/test_composer_helpers.py -v`
Expected: All composer tests PASS, including the new one. The previous `test_compose_slide_returns_composed_slide` test will also need updating since `compose_slide` now returns a tuple — update its last line to:

```python
    out, _warnings = compose_slide(
        slide_index=0, slide_plan=slide_plan, codename="Project Halo",
        docs=docs, web_snippets=[],
        sector="SaaS", out_dir=tmp_path,
    )
    assert out.title == "Business Profile"
    assert out.sections[0].bullets[0].text.startswith("Mid-cap")
```

Re-run `pytest tests/unit/test_composer_helpers.py -v` after that fix. Expected: all green.

- [ ] **Step 7: Confirm full suite still green**

Run: `pytest -v`
Expected: 107 passed (101 baseline + 5 new tests + 1 from Task 4's second test = 107).

If any other test file calls `compose_slide` directly (rare; check with `grep -rn "compose_slide(" tests/`), update its unpack too. The end-to-end `test_cli_smoke.py` does not call `compose_slide` directly — it goes through the graph — so changes in the node wrapper (Step 5) should keep it green.

- [ ] **Step 8: Commit**

```bash
git add src/kelp_teaser/agents/composer.py tests/unit/test_composer_helpers.py
git commit -m "$(cat <<'EOF'
feat(composer): surface ChartDesigner/ImageCurator failures as warnings

compose_slide now returns (ComposedSlide, list[str]) so transient
sub-agent failures (a chart or image silently dropped) are visible in
the trace step instead of only in logs. The Composer node writes the
warning list into trace.json under the per-slide composer step.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Stage 1 closeout

- [ ] **Final full-suite run**

Run: `pytest -v`
Expected: 107 passed.

- [ ] **`git status` is clean**

Run: `git status`
Expected: `nothing to commit, working tree clean`. No stray output folders in `data/outputs/`; if any appeared during testing (they shouldn't — tests use `tmp_path`), investigate before continuing.

- [ ] **5 commits land on the branch**

Run: `git log --oneline -n 7`
Expected: The most recent 5 commits are the ones from Tasks 1–5 in order, atop `58d28e3 docs: add CLAUDE.md and PROMPT.md for cross-session handoff`.

- [ ] **Hand off to Stage 2**

Stage 2 in [PROMPT.md](../../../PROMPT.md) is the first live Gemini run on Ksolves. Stage 2 is a *manual* phase (no plan needed) — the user drives it interactively with `kelp-teaser run data/inputs/Ksolves/` after configuring `.env`. Do not start Stage 2 in the same session unless the user explicitly asks.

---

## Self-review notes (already applied)

- **Spec coverage:** All 5 polish items from [phase_c_polish_items.md](../../../../.claude/projects/c--Users-Rishabh-Kumar-PPT-Hackathon-AI-ML-GC-RND/memory/phase_c_polish_items.md) and PROMPT.md Stage 1 map to Tasks 1–5 respectively (Critic → 1, Trace cost → 2, Researcher warning → 3, Renderer index assert → 4, Composer sub-call → 5).
- **Type consistency:** `CriticIssue` field names match `schemas/critic.py` (`severity`, `category`, `detail`, `suggested_fix`, `slide_index`). `TraceWriter.add_cost(usd: float)` matches `graph/trace.py:39`. `compose_slide` return-type change is propagated to the test and to the caller-update step.
- **No placeholders:** Every code block contains actual code. Every command has an expected outcome.
- **Caller-update step (Task 5 Step 5) is intentionally generic** because the node wrapper lives outside the file we know exactly; the engineer is told to `grep` first and apply a small, well-specified change to each call site. This is unavoidable without knowing the exact node-wrapping code, and the grep step makes the work concrete.
