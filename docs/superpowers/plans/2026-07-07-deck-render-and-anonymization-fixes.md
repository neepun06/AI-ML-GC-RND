# Deck Render & Anonymization Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the rendered teaser deck score well against the Kelp hackathon rubric — charts that actually display data (30% criterion), a sample-like multi-panel layout, undistorted full-bleed images, and genuinely blind anonymization (15% criterion).

**Architecture:** All rendering changes are concentrated in `src/kelp_teaser/render/` (chiefly `deck.py`, plus `slide_components.py` and `charts.py`). The layout engine moves from naive equal-height rows to weighted rows plus two composite panel layouts (chart+commentary, badge grid). Anonymization is fixed in `agents/anonymizer.py` by broadening the scrub trigger beyond the literal company name to include identifying entities (award names, product names). The pipeline topology, schemas, and Planner are unchanged — the dynamic Planner remains the sector-adaptability differentiator.

**Tech Stack:** Python 3.11, python-pptx, Pydantic v2, LangGraph, pytest. Tests build real `.pptx` into `tmp_path` and assert on shape geometry; LLM calls are stubbed via `tests.fixtures.stub_llm.patch_llm()`.

---

## File Structure

- `src/kelp_teaser/render/deck.py` — **modified.** Replace equal-row layout with weighted rows; add composite chart+commentary and badge-grid layouts; dispatch per section-kind.
- `src/kelp_teaser/render/slide_components.py` — **modified.** Add `add_picture_cover()` (aspect-preserving image fit) and `draw_badge_grid()` helper.
- `src/kelp_teaser/render/charts.py` — **modified.** Add value data labels + hide/soften axes so short charts still read; no signature change.
- `src/kelp_teaser/agents/anonymizer.py` — **modified.** Broaden the scrub trigger; scrub bullet AND metric-value/label text against an identifier list.
- `src/kelp_teaser/graph/state.py` — **modified.** Add optional `identifier_terms: list[str]` carried from Planner/Researcher for the anonymizer to scrub.
- Tests: `tests/unit/test_deck_render.py`, `tests/unit/test_slide_components.py` (new), `tests/unit/test_charts.py`, `tests/unit/test_anonymizer.py`.

Section-kind → layout weight (used by Task 1):

| kind | weight | rationale |
|---|---|---|
| `chart` | 3 | needs vertical room to draw bars/lines |
| `hero_image` | 3 | full-bleed visual |
| `quadrant` | 3 | 2×2 grid needs height |
| `bullet_list` | 2 | text block |
| `product_grid` | 2 | text grid |
| `metric_tile` | 1 | short tile row |
| `kpi_strip` | 1 | short tile row |

---

## Task 1: Weighted-row layout so charts get real height

**Why:** `_render_slide` currently splits the content area into N *equal* rows. On a 4-section slide a chart gets ~0.7" of height and renders only its title+axis (no bars). Weighting rows by section kind gives charts a tall row and KPI strips a short one.

**Files:**
- Modify: `src/kelp_teaser/render/deck.py:46-63`
- Test: `tests/unit/test_deck_render.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_deck_render.py`:

```python
def _chart_slide() -> ComposedSlide:
    from kelp_teaser.schemas.slide import ChartSpec, ChartSeries
    from kelp_teaser.schemas.plan import ChartKind
    chart = ChartSpec(
        chart_kind=ChartKind.revenue_growth_bar,
        title="Revenue",
        categories=["FY23", "FY24", "FY25"],
        series=[ChartSeries(name="Revenue", values=[10.0, 20.0, 30.0])],
        source_id="doc:x.md",
    )
    return ComposedSlide(index=0, title="Financials", sections=[
        ComposedSection(kind=ComponentKind.chart, heading="Revenue", chart=chart),
        ComposedSection(kind=ComponentKind.kpi_strip, metrics=[
            MetricTile(value="30", label="Rev", source_id="doc:x.md"),
        ]),
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="x", source_id="doc:x.md"),
        ]),
    ])


def test_chart_row_is_taller_than_kpi_row(tmp_path):
    """A chart section must be allocated a taller frame than a kpi_strip
    section on the same slide (weighted rows, not equal rows)."""
    from pptx import Presentation
    out = render_deck(slides=[_chart_slide()], codename="Project X",
                      out_path=tmp_path / "d.pptx")
    prs = Presentation(str(out))
    slide = prs.slides[0]
    chart_h = next(sh.height for sh in slide.shapes if sh.has_chart)
    # The chart must have real vertical room — at least 1.8 inches.
    assert chart_h >= Inches(1.8), f"chart too short: {chart_h} EMU"
```

Ensure the test file imports `MetricTile` and `Inches`:

```python
from pptx.util import Inches
from kelp_teaser.schemas.slide import Bullet, ComposedSection, ComposedSlide, MetricTile
from kelp_teaser.schemas.plan import ComponentKind
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_deck_render.py::test_chart_row_is_taller_than_kpi_row -v`
Expected: FAIL — chart height ≈ 0.7" (640080 EMU), well under `Inches(1.8)` (1645920 EMU).

- [ ] **Step 3: Implement weighted rows in `deck.py`**

Replace `_render_slide` at [src/kelp_teaser/render/deck.py:46-63](src/kelp_teaser/render/deck.py#L46-L63) with:

```python
# Height weight per section kind. Charts/images/quadrants need real vertical
# room; metric/kpi strips are short. Bullets are medium.
_ROW_WEIGHTS: dict[ComponentKind, int] = {
    ComponentKind.chart: 3,
    ComponentKind.hero_image: 3,
    ComponentKind.quadrant: 3,
    ComponentKind.bullet_list: 2,
    ComponentKind.product_grid: 2,
    ComponentKind.metric_tile: 1,
    ComponentKind.kpi_strip: 1,
}


def _render_slide(prs, composed: ComposedSlide, codename: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = theme.PALETTE["bg_slide"]

    add_header(slide, codename=codename, subtitle=composed.title)
    add_footer(slide)

    content_h = theme.SLIDE_H - theme.HEADER_HEIGHT - Inches(0.6)
    weights = [_ROW_WEIGHTS.get(s.kind, 2) for s in composed.sections]
    total_weight = sum(weights) or 1
    y_cursor = theme.HEADER_HEIGHT + Inches(0.2)

    for section, weight in zip(composed.sections, weights):
        row_h = content_h * weight / total_weight
        _render_section(slide, section,
                        x=theme.MARGIN, y=y_cursor,
                        w=theme.CONTENT_W, h=row_h - Inches(0.1))
        y_cursor += row_h
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_deck_render.py -v`
Expected: All deck-render tests PASS, including the new one.

- [ ] **Step 5: Confirm full suite still green**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: all pass (110 baseline + 1 new = 111).

- [ ] **Step 6: Commit**

```bash
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com add src/kelp_teaser/render/deck.py tests/unit/test_deck_render.py
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com commit -m "$(cat <<'EOF'
fix(render): weight section row heights so charts get real vertical space

Equal-height rows starved charts to ~0.7in on multi-section slides, so
only the axis/title drew and no bars/lines were visible. Weight rows by
section kind (chart/image/quadrant tall, kpi/metric short). Fixes the
rubric's 30% "native charts" criterion.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Chart data labels + softened axes so charts read clearly

**Why:** The sample deck shows value labels on bars (55, 62, 70…). Adding data labels and de-emphasizing the numeric axis makes charts legible and closer to the sample, and guards against any remaining short-frame cases.

**Files:**
- Modify: `src/kelp_teaser/render/charts.py:39-49`
- Test: `tests/unit/test_charts.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_charts.py`:

```python
def test_bar_chart_has_data_labels(tmp_path):
    """Column/line charts must show value data labels so numbers are
    readable without reading the axis."""
    from pptx import Presentation
    from pptx.util import Inches
    from kelp_teaser.render.charts import render_chart
    from kelp_teaser.schemas.slide import ChartSpec, ChartSeries
    from kelp_teaser.schemas.plan import ChartKind

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    spec = ChartSpec(
        chart_kind=ChartKind.revenue_growth_bar, title="Rev",
        categories=["FY23", "FY24"], 
        series=[ChartSeries(name="Revenue", values=[10.0, 20.0])],
        source_id="doc:x.md",
    )
    render_chart(slide, Inches(1), Inches(1), Inches(5), Inches(3), spec)
    chart = next(sh.chart for sh in slide.shapes if sh.has_chart)
    plot = chart.plots[0]
    assert plot.has_data_labels is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_charts.py::test_bar_chart_has_data_labels -v`
Expected: FAIL — `has_data_labels` is `False` by default.

- [ ] **Step 3: Add data labels in `charts.py`**

In [src/kelp_teaser/render/charts.py](src/kelp_teaser/render/charts.py#L42), after the title block (after the `if spec.title:` block, before the donut-legend block), insert:

```python
    # Value data labels on bar/line charts (donuts get legend instead).
    if spec.chart_kind not in (ChartKind.segment_mix_donut,
                               ChartKind.channel_mix_donut):
        plot = chart.plots[0]
        plot.has_data_labels = True
        plot.data_labels.number_format = "General"
        plot.data_labels.number_format_is_linked = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_charts.py -v`
Expected: All chart tests PASS.

- [ ] **Step 5: Confirm full suite still green**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: 112 passed.

- [ ] **Step 6: Commit**

```bash
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com add src/kelp_teaser/render/charts.py tests/unit/test_charts.py
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com commit -m "$(cat <<'EOF'
feat(render): add value data labels to bar/line charts

Match the sample deck's readability — show the value on each bar/point
so the chart reads without parsing the axis.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Aspect-preserving image fit (no more squashed photos)

**Why:** `_render_section`'s hero_image branch calls `add_picture(path, x, y, width=w, height=h)`, forcing the photo into the box and distorting it. A cover-fit helper scales to fill the box by the larger ratio and centers, preserving aspect (full-bleed look the brief wants).

**Files:**
- Modify: `src/kelp_teaser/render/slide_components.py` (add `add_picture_cover`)
- Modify: `src/kelp_teaser/render/deck.py:87-98` (call it)
- Test: `tests/unit/test_slide_components.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_slide_components.py`:

```python
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from kelp_teaser.render.slide_components import add_picture_cover


def _make_wide_image(path: Path) -> None:
    # 400x100 — a 4:1 wide image.
    Image.new("RGB", (400, 100), (120, 120, 200)).save(path)


def test_add_picture_cover_preserves_aspect_ratio(tmp_path):
    """A 4:1 image placed in a 2:1 box must keep its 4:1 aspect ratio
    (scaled to cover), not be squashed to the box ratio."""
    img = tmp_path / "wide.png"
    _make_wide_image(img)

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    # Box is 6in x 3in (2:1).
    pic = add_picture_cover(slide, str(img),
                            Inches(1), Inches(1), Inches(6), Inches(3))
    ratio = pic.width / pic.height
    assert abs(ratio - 4.0) < 0.05, f"aspect not preserved: {ratio}"
```

Note: `Pillow` (`PIL`) ships with python-pptx's deps; confirm with `venv/Scripts/python.exe -c "import PIL"`. If missing, run `venv/Scripts/python.exe -m pip install pillow` and note it in the commit.

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_slide_components.py -v`
Expected: FAIL — `add_picture_cover` does not exist (ImportError).

- [ ] **Step 3: Implement `add_picture_cover` in `slide_components.py`**

Add to `src/kelp_teaser/render/slide_components.py` (add `from PIL import Image` at top):

```python
def add_picture_cover(slide, image_path: str, x, y, w, h):
    """Place an image filling the (x,y,w,h) box while preserving aspect
    ratio (scale-to-cover, centered). Returns the picture shape.

    The image is scaled so the box is fully covered; overflow is centered.
    This avoids the squashing that add_picture(width=w, height=h) causes.
    """
    with Image.open(image_path) as im:
        iw, ih = im.size
    box_ratio = w / h
    img_ratio = iw / ih
    if img_ratio > box_ratio:
        # Image is wider than box: match height, overflow width.
        new_h = h
        new_w = int(h * img_ratio)
    else:
        # Image is taller than box: match width, overflow height.
        new_w = w
        new_h = int(w / img_ratio)
    px = int(x - (new_w - w) / 2)
    py = int(y - (new_h - h) / 2)
    return slide.shapes.add_picture(image_path, px, py, int(new_w), int(new_h))
```

- [ ] **Step 4: Call it from `deck.py`**

In [src/kelp_teaser/render/deck.py:92-94](src/kelp_teaser/render/deck.py#L92-L94), replace:

```python
        if image_path.is_file():
            slide.shapes.add_picture(str(image_path), x, y, width=w, height=h)
```

with:

```python
        if image_path.is_file():
            add_picture_cover(slide, str(image_path), x, y, w, h)
```

And add `add_picture_cover` to the import block at [src/kelp_teaser/render/deck.py:15-21](src/kelp_teaser/render/deck.py#L15-L21).

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_slide_components.py tests/unit/test_deck_render.py -v`
Expected: PASS.

- [ ] **Step 6: Confirm full suite still green**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: 113 passed.

- [ ] **Step 7: Commit**

```bash
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com add src/kelp_teaser/render/slide_components.py src/kelp_teaser/render/deck.py tests/unit/test_slide_components.py
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com commit -m "$(cat <<'EOF'
fix(render): scale hero images to cover box without distortion

add_picture(width=w, height=h) stretched photos to the row's aspect
ratio, squashing them. add_picture_cover scales to cover and centers,
preserving aspect for a clean full-bleed look.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Composite chart + commentary panel layout

**Why:** The sample's financial slide is a big chart on the left with commentary/callout panels on the right — not stacked full-width rows. Add a composite layout so a `chart` section immediately followed by a `bullet_list` section renders side-by-side, matching the sample and using horizontal space.

This is scoped narrowly: a single new render path triggered when a slide has exactly the pattern [chart, bullet_list] adjacent. It does not change the Planner or schemas.

**Files:**
- Modify: `src/kelp_teaser/render/deck.py` (`_render_slide` — detect and render the pair)
- Test: `tests/unit/test_deck_render.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_deck_render.py`:

```python
def test_chart_then_bullets_render_side_by_side(tmp_path):
    """When a chart section is immediately followed by a bullet_list, they
    render in the same horizontal band (chart on left half, bullets on
    right half) rather than stacked full width."""
    from pptx import Presentation
    from kelp_teaser.schemas.slide import ChartSpec, ChartSeries
    from kelp_teaser.schemas.plan import ChartKind
    chart = ChartSpec(chart_kind=ChartKind.revenue_growth_bar, title="Rev",
                      categories=["FY24", "FY25"],
                      series=[ChartSeries(name="R", values=[1.0, 2.0])],
                      source_id="doc:x.md")
    slide = ComposedSlide(index=0, title="Fin", sections=[
        ComposedSection(kind=ComponentKind.chart, heading="Rev", chart=chart),
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="commentary", source_id="doc:x.md")]),
    ])
    out = render_deck(slides=[slide], codename="Project X",
                      out_path=tmp_path / "d.pptx")
    prs = Presentation(str(out))
    s = prs.slides[0]
    chart_shape = next(sh for sh in s.shapes if sh.has_chart)
    # Chart occupies roughly the left half, not the full content width.
    assert chart_shape.width < theme.CONTENT_W * 0.65
```

Add `from kelp_teaser.render import theme` to the test imports if not present.

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_deck_render.py::test_chart_then_bullets_render_side_by_side -v`
Expected: FAIL — chart currently spans full `CONTENT_W`.

- [ ] **Step 3: Add the composite pair detection to `_render_slide`**

Replace the section-iteration loop in `_render_slide` (the `for section, weight in zip(...)` block from Task 1) with a version that greedily renders a [chart, bullet_list] pair side-by-side:

```python
    sections = composed.sections
    i = 0
    while i < len(sections):
        sec = sections[i]
        nxt = sections[i + 1] if i + 1 < len(sections) else None
        # Composite: chart + adjacent bullet_list -> side-by-side band.
        if (sec.kind == ComponentKind.chart
                and nxt is not None
                and nxt.kind == ComponentKind.bullet_list):
            band_weight = _ROW_WEIGHTS[ComponentKind.chart]
            row_h = content_h * band_weight / total_weight
            half_w = (theme.CONTENT_W - theme.GUTTER) / 2
            _render_section(slide, sec, x=theme.MARGIN, y=y_cursor,
                            w=half_w, h=row_h - Inches(0.1))
            _render_section(slide, nxt,
                            x=theme.MARGIN + half_w + theme.GUTTER, y=y_cursor,
                            w=half_w, h=row_h - Inches(0.1))
            y_cursor += row_h
            i += 2
            continue
        weight = _ROW_WEIGHTS.get(sec.kind, 2)
        row_h = content_h * weight / total_weight
        _render_section(slide, sec, x=theme.MARGIN, y=y_cursor,
                        w=theme.CONTENT_W, h=row_h - Inches(0.1))
        y_cursor += row_h
        i += 1
```

For weight bookkeeping: change `total_weight` so a side-by-side pair only counts the chart's weight once. Compute it after building a per-render-unit weight list. Replace the `weights`/`total_weight` computation (from Task 1) with:

```python
    # Build render units: a [chart, bullet_list] pair is one unit weighted
    # by the chart; everything else is its own unit.
    render_weights: list[int] = []
    j = 0
    secs = composed.sections
    while j < len(secs):
        if (secs[j].kind == ComponentKind.chart
                and j + 1 < len(secs)
                and secs[j + 1].kind == ComponentKind.bullet_list):
            render_weights.append(_ROW_WEIGHTS[ComponentKind.chart])
            j += 2
        else:
            render_weights.append(_ROW_WEIGHTS.get(secs[j].kind, 2))
            j += 1
    total_weight = sum(render_weights) or 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_deck_render.py -v`
Expected: All deck-render tests PASS.

- [ ] **Step 5: Confirm full suite still green**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: 114 passed.

- [ ] **Step 6: Commit**

```bash
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com add src/kelp_teaser/render/deck.py tests/unit/test_deck_render.py
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com commit -m "$(cat <<'EOF'
feat(render): side-by-side chart + commentary band

Match the sample deck's financial slide: a chart followed by a bullet
list renders as a left-chart / right-commentary band instead of two
stacked full-width rows, using horizontal space and improving density.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Broaden anonymizer to scrub identifying entities, not just the literal name

**Why:** `_scrub_text` returns early unless the text literally contains the company name (`if real_name.lower() not in text.lower(): return text`). So "NASSCOM Impact Award 2025", "Dashboard Ninja", "DFM" pass through untouched — exactly the leaks the Critic flags as blocking. We pass a list of identifier terms (award names, product names, distinctive brand tokens) and scrub any text containing one of them, reusing the existing LLM generalization prompt.

**Files:**
- Modify: `src/kelp_teaser/graph/state.py` (add `identifier_terms`)
- Modify: `src/kelp_teaser/agents/anonymizer.py` (`run` + `_scrub_text` accept identifier terms)
- Test: `tests/unit/test_anonymizer.py` (append)

- [ ] **Step 1: Add `identifier_terms` to GraphState**

In `src/kelp_teaser/graph/state.py`, in the anonymization-related fields block (near `anonymization_log` at line 38), add:

```python
    identifier_terms: list[str] = Field(
        default_factory=list,
        description="Distinctive tokens (award names, product names) that "
        "unblind the company and must be generalized by the Anonymizer.",
    )
```

- [ ] **Step 2: Write the failing test**

Append to `tests/unit/test_anonymizer.py` (mirror the existing test setup in that file for `GraphState` construction and `patch_llm`):

```python
def test_anonymizer_scrubs_identifier_terms_not_containing_company_name(
    monkeypatch,
):
    """A bullet that names a distinctive award (but not the company name)
    must still be sent to the scrubber when the award is an identifier
    term."""
    from kelp_teaser.agents import anonymizer
    from kelp_teaser.schemas.slide import Bullet, ComposedSection, ComposedSlide
    from kelp_teaser.schemas.plan import ComponentKind

    seen: list[str] = []

    def fake_complete_json(model, prompt, schema, **kw):
        # Record what text was sent and return a generalized replacement.
        seen.append(prompt)
        return schema(replacement="Won a leading industry growth award.")

    monkeypatch.setattr(anonymizer.llm, "complete_json", fake_complete_json)

    slide = ComposedSlide(index=0, title="t", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="Won NASSCOM Impact Award 2025 for Growth.",
                   source_id="doc:x.md"),
        ]),
    ])
    state = _state_with_slides({0: slide})  # helper already in this test file
    state = state.model_copy(update={
        "company_name": "Ksolves",
        "identifier_terms": ["NASSCOM Impact Award"],
    })

    result = anonymizer.run(state)
    out_slide = result["composed_slides"][0]
    assert "NASSCOM" not in out_slide.sections[0].bullets[0].text
    assert len(seen) == 1  # scrubber WAS called despite no company name
```

If the existing test file has no `_state_with_slides` helper, define one at the top of the file mirroring how other tests build a `GraphState` (see the imports and `_state(...)` usage already present in `tests/unit/test_anonymizer.py`).

- [ ] **Step 3: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_anonymizer.py::test_anonymizer_scrubs_identifier_terms_not_containing_company_name -v`
Expected: FAIL — `seen` is empty (scrubber never called) because the text lacks "Ksolves", so `_scrub_text` returns early.

- [ ] **Step 4: Broaden the scrub trigger in `anonymizer.py`**

Change `run` to read `identifier_terms` from state and thread them through. Replace the signature and body of `_scrub_text` at [src/kelp_teaser/agents/anonymizer.py:62-74](src/kelp_teaser/agents/anonymizer.py#L62-L74) with:

```python
def _scrub_text(text: str, real_name: str, codename: str,
                identifier_terms: list[str] | None = None) -> str:
    terms = identifier_terms or []
    lower = text.lower()
    triggers = [real_name] + terms
    if not any(t and t.lower() in lower for t in triggers):
        return text
    prompt = load_prompt("anonymizer").render(
        real_name=real_name, codename=codename, original_text=text,
    )
    try:
        out = llm.complete_json(MODEL_FAST, prompt, _Replacement)
        return out.replacement or text
    except Exception as e:  # noqa: BLE001
        log.error("Anonymizer call failed: %s", e)
        return _literal_swap(text, real_name, codename)
```

In `run`, read the terms once and pass them into `_scrub_bullet` / `_scrub_metric`. Update those two helpers to accept and forward `identifier_terms` to `_scrub_text`. Concretely, in `run` add near the top:

```python
    identifier_terms = state.identifier_terms
```

and change the two comprehension calls to pass `identifier_terms=identifier_terms`, and update `_scrub_bullet` / `_scrub_metric` signatures to accept `identifier_terms: list[str]` and forward it to each `_scrub_text(...)` call.

- [ ] **Step 5: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_anonymizer.py -v`
Expected: All anonymizer tests PASS.

- [ ] **Step 6: Confirm full suite still green**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: 115 passed.

- [ ] **Step 7: Commit**

```bash
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com add src/kelp_teaser/graph/state.py src/kelp_teaser/agents/anonymizer.py tests/unit/test_anonymizer.py
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com commit -m "$(cat <<'EOF'
fix(anonymizer): scrub identifying entities, not just the literal name

The scrubber returned early unless the text contained the company name,
so award/product names (NASSCOM Impact Award, Dashboard Ninja, DFM)
leaked into the "blind" deck and the Critic flagged them as blocking.
Also scrub text containing any identifier_term carried on GraphState.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Planner/Researcher populate `identifier_terms`

**Why:** Task 5 consumes `state.identifier_terms` but nothing sets it. The Planner already reads the full brief and assigns a codename; have it also emit the distinctive tokens it saw (awards, product names) so the Anonymizer can scrub them. Smallest viable wiring: add an `identifier_terms` field to `DeckPlan` and copy it onto state in the planner node.

**Files:**
- Modify: `src/kelp_teaser/schemas/plan.py` (add `identifier_terms` to `DeckPlan`)
- Modify: `src/kelp_teaser/agents/planner.py` (return `identifier_terms` in the dict)
- Modify: `prompts/planner.md` (ask for the terms)
- Test: `tests/unit/test_planner.py` (append)

- [ ] **Step 1: Add the field to `DeckPlan`**

In `src/kelp_teaser/schemas/plan.py`, add to the `DeckPlan` model:

```python
    identifier_terms: list[str] = Field(
        default_factory=list,
        description="Distinctive names that would unblind the company "
        "(awards, product/brand names, trademarks) for the Anonymizer.",
    )
```

- [ ] **Step 2: Write the failing test**

Append to `tests/unit/test_planner.py` (mirror the existing planner test's stub setup):

```python
def test_planner_surfaces_identifier_terms(monkeypatch):
    """The planner node must copy DeckPlan.identifier_terms onto the
    returned state dict so the Anonymizer can consume them."""
    from kelp_teaser.agents import planner
    from kelp_teaser.schemas.plan import DeckPlan, SlidePlan, SectionPlan, ComponentKind

    plan = DeckPlan(
        codename="Project X",
        identifier_terms=["Dashboard Ninja", "NASSCOM Impact Award"],
        slides=[SlidePlan(title=f"S{i}", sections=[
            SectionPlan(kind=ComponentKind.bullet_list, data_hooks=["x"])
        ]) for i in range(3)],
    )
    patch_llm(monkeypatch, json_responses=[plan])
    state = _planner_state()  # helper already in this test file
    result = planner.run(state)
    assert result["identifier_terms"] == ["Dashboard Ninja", "NASSCOM Impact Award"]
```

If `_planner_state` does not exist, build a `GraphState` inline as the other tests in the file do (with `sector`, `planner_brief`, etc. set).

- [ ] **Step 3: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_planner.py::test_planner_surfaces_identifier_terms -v`
Expected: FAIL — the planner node's returned dict has no `identifier_terms` key.

- [ ] **Step 4: Return the terms from the planner node**

In `src/kelp_teaser/agents/planner.py`, find where `run` returns its dict (it returns `{"plan": plan, ...}`). Add `identifier_terms` to that dict:

```python
    return {"plan": plan, "identifier_terms": plan.identifier_terms}
```

(If the return dict has other keys, preserve them and just add this one.)

- [ ] **Step 5: Ask for the terms in the prompt**

In `prompts/planner.md`, add a rule instructing the model to populate `identifier_terms`:

```markdown
- Populate `identifier_terms` with the distinctive proper nouns you saw that
  would unblind the company: award names, product/brand names, trademarks,
  and unique certifications. These are generalized later by the Anonymizer.
```

- [ ] **Step 6: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_planner.py -v`
Expected: All planner tests PASS.

- [ ] **Step 7: Confirm full suite still green**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: 116 passed.

- [ ] **Step 8: Commit**

```bash
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com add src/kelp_teaser/schemas/plan.py src/kelp_teaser/agents/planner.py prompts/planner.md tests/unit/test_planner.py
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com commit -m "$(cat <<'EOF'
feat(planner): surface identifier_terms for anonymization

The Planner now emits the distinctive proper nouns (awards, product and
brand names) it observed, carried on state so the Anonymizer generalizes
them and the deck is genuinely blind.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Branding audit against Attachment A

**Why:** The rubric enforces Kelp branding (logo top of every slide, 9pt centered footer, Arial headings 20-24 / body 10-12, indigo header, white body). Most is already in `theme.py`/`slide_components.py`; this task verifies compliance with an automated test rather than by eye.

**Files:**
- Test: `tests/unit/test_branding.py` (new)
- Modify (only if the test fails): `src/kelp_teaser/render/slide_components.py` / `theme.py`

- [ ] **Step 1: Write the branding test**

Create `tests/unit/test_branding.py`:

```python
from pptx import Presentation
from pptx.util import Pt

from kelp_teaser.render import theme
from kelp_teaser.render.deck import render_deck
from kelp_teaser.schemas.slide import Bullet, ComposedSection, ComposedSlide
from kelp_teaser.schemas.plan import ComponentKind


def _slide(i):
    return ComposedSlide(index=i, title=f"S{i}", sections=[
        ComposedSection(kind=ComponentKind.bullet_list, bullets=[
            Bullet(text="x", source_id="doc:x.md")]),
    ])


def test_every_slide_has_footer_and_logo(tmp_path):
    out = render_deck(slides=[_slide(0), _slide(1), _slide(2)],
                      codename="Project X", out_path=tmp_path / "d.pptx")
    prs = Presentation(str(out))
    for slide in prs.slides:
        texts = [sh.text_frame.text for sh in slide.shapes
                 if sh.has_text_frame]
        assert any(theme.FOOTER_TEXT in t for t in texts), "footer missing"
        assert any(theme.LOGO_PLACEHOLDER_TEXT == t.strip() for t in texts), \
            "logo placeholder missing"


def test_footer_is_9pt():
    assert theme.FOOTER_FONT_SIZE == Pt(9)


def test_fonts_are_arial():
    assert theme.HEADING_FONT == "Arial"
    assert theme.BODY_FONT == "Arial"
```

- [ ] **Step 2: Run the test**

Run: `venv/Scripts/python.exe -m pytest tests/unit/test_branding.py -v`
Expected: If all PASS, branding already compliant — skip to Step 4. If any FAIL, fix the specific constant/component in Step 3.

- [ ] **Step 3: Fix any failure**

Only if a branding test failed: adjust the offending value in `theme.py` (e.g. font name, footer size) or `slide_components.py` (e.g. ensure `add_footer`/`add_header` are called for every slide — they already are in `_render_slide`). Make the minimal change to pass, re-run Step 2.

- [ ] **Step 4: Confirm full suite still green**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: 119 passed (116 + 3 branding tests).

- [ ] **Step 5: Commit**

```bash
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com add tests/unit/test_branding.py src/kelp_teaser/render/
git -c user.name=SirCoolerArc -c user.email=rishabhxkumar@gmail.com commit -m "$(cat <<'EOF'
test(render): lock Kelp branding compliance (footer, logo, fonts)

Automated checks for the rubric's branding requirements: 9pt centered
footer and Kelp logo on every slide, Arial headings/body.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Live end-to-end verification

**Why:** Unit tests assert geometry, but only a real run proves the deck looks right. Regenerate the Ksolves deck and inspect it.

- [ ] **Step 1: Run the pipeline live**

Run: `venv/Scripts/kelp-teaser.exe run "data/inputs/Ksolves/"`
Expected: exit 0, "Wrote ...teaser.pptx / citations.docx / trace.json", cost well under ₹100 (~$0.01–0.02).

- [ ] **Step 2: Inspect the rendered deck programmatically**

Run this and confirm charts have real height and the deck has images:

```bash
venv/Scripts/python.exe -c "
from pptx import Presentation, util
import glob, os
d = sorted(glob.glob('data/outputs/Ksolves_*'), key=os.path.getmtime)[-1]
prs = Presentation(d + '/teaser.pptx')
for i, s in enumerate(prs.slides):
    charts = [sh for sh in s.shapes if sh.has_chart]
    pics = [sh for sh in s.shapes if sh.shape_type == 13]
    for c in charts:
        print(f'slide {i} chart h={c.height/914400:.2f}in (must be >1.8)')
    print(f'slide {i}: charts={len(charts)} pics={len(pics)}')
"
```
Expected: every chart height > 1.8in; images present on image slides.

- [ ] **Step 3: Open the deck and eyeball it**

Open the newest `data/outputs/Ksolves_*/teaser.pptx` in PowerPoint. Confirm: charts show bars/lines with data labels; images are not squashed; no real company name / award / product-name leaks; footer + logo on every slide.

- [ ] **Step 4: Check the trace for residual leaks**

Run: inspect the newest `trace.json` critic step. Expected: fewer or zero blocking anonymization issues than the pre-fix baseline (which had 2 blocking). Note any remaining leaks for a follow-up.

- [ ] **Step 5: Final full-suite run**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: 119 passed.

---

## Self-Review Notes (already applied)

- **Spec coverage:** Charts render (Tasks 1, 2) → rubric 30%. Side-by-side panels (Task 4) → sample-like layout. Image aspect (Task 3) → branding imagery. Anonymization (Tasks 5, 6) → rubric 15% + spec goal #4. Branding audit (Task 7) → Attachment A. Live verify (Task 8). Batch generation intentionally excluded per user decision (run one-by-one).
- **Type consistency:** `identifier_terms: list[str]` is defined on `GraphState` (Task 5) and `DeckPlan` (Task 6), consumed in `anonymizer.run`/`_scrub_text` (Task 5), produced in `planner.run` (Task 6). `add_picture_cover(slide, path, x, y, w, h)` defined in Task 3, called in Task 3 Step 4. `_ROW_WEIGHTS` defined in Task 1, reused in Task 4.
- **Test counts** are cumulative estimates; the exact baseline is whatever `pytest -q` reports before Task 1 (was 110). Each task adds the tests it introduces.
- **Non-goals honored:** no revision loop, no Planner structural rewrite, no new chart kinds, no batch command. The dynamic Planner (adaptability differentiator, 25%) is preserved.
