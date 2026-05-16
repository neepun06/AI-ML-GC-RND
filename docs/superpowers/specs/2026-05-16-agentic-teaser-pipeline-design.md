# Kelp Teaser Pipeline v2 — Agentic Revamp

**Status:** Design approved, ready for implementation planning
**Date:** 2026-05-16
**Author:** Rishabh Kumar
**Context:** Post-hackathon revamp of [AI-ML-GC-RND](https://github.com/neepun06/AI-ML-GC-RND). The hackathon submission was a fixed 4-slide linear pipeline. This v2 replaces it with a LangGraph-orchestrated multi-agent system that composes each deck dynamically based on sector and data richness.

---

## 1. Goals and non-goals

### Goals

1. **Fully dynamic slide composition.** No fixed templates. A Planner agent decides, per company, which sections exist, in what order, and which visual components (chart vs. table vs. metric tile vs. quadrant grid vs. hero image) each section uses.
2. **Clean folder structure.** All source under `src/kelp_teaser/`, prompts in `prompts/`, inputs under `data/inputs/`, outputs under `data/outputs/{company}_{run_id}/`. No scripts or generated artifacts at the repo root.
3. **Genuine citation integrity.** Every textual claim on a slide is born with a `source_id`, validated by Pydantic, and reflected as a row in a structured Citations document linking claim → source → verbatim quote.
4. **Blind teaser.** Real company name never appears on the rendered deck. Codename is assigned by the Planner; an Anonymizer pass scrubs identifying tokens; the Critic spot-checks for residual leaks.
5. **Per-teaser runtime cost ≤ ~$0.40** on Gemini API.
6. **Resume-quality artifact.** The system must read as "I built an agentic pipeline with LangGraph" — explicit state machine, specialized agents, conditional routing, traceability.

### Non-goals (explicit out-of-scope)

- Web UI / dashboard. CLI only.
- Multi-company batch mode in a single process. Shell loop is fine.
- Authenticated paid data sources (Bloomberg, Crunchbase).
- Model fine-tuning.
- Streaming progress UI.
- Multi-provider model fallback. Gemini-only at runtime. (Claude Opus 4.7 is used at build time via Claude Code, not at runtime.)
- Vector DB / RAG. Data packs fit in Gemini Pro's context window directly.
- Visible citation superscripts on slides. Citations live in the Word doc only.
- Visual quality test automation. Smoke test only verifies artifacts exist and trace is well-formed.

---

## 2. High-level architecture

A LangGraph state machine orchestrates 9 specialized agents over a shared `GraphState` (Pydantic). Each agent is a pure function `(GraphState) → partial GraphState`. Two pure renderers (no LLM) consume the final state to produce the `.pptx` and `.docx`.

### Graph topology

```
Ingestor → Researcher → SectorClassifier → Planner
  → [Composer × N slides, parallel fan-out via Send]
      ↳ each slide internally calls ChartDesigner and/or ImageCurator
  → Anonymizer → Critic (single pass, no loop)
  → CitationTracker → DeckRenderer → CitationDocRenderer → END
```

### Key properties

- **Dynamic composition:** Planner output (`DeckPlan`) varies per company. No company gets the same slide structure as another.
- **Parallel slide composition:** Composer fans out across slides via LangGraph's `Send`, reducing wall-clock time roughly 2–3×.
- **Single-pass Critic, no loop:** Critic emits a report; unresolved issues are logged to the trace. Flow continues unconditionally.
- **Single source of truth:** `GraphState` carries everything. Agents read what they need, write back named fields. No global mutable state.
- **Full traceability:** every agent's input/output is written to `data/outputs/{company}_{run_id}/intermediate/{step:02d}_{agent}.json`. A top-level `trace.json` records timings, model IDs, token counts, and an estimated cost.

### LLM model mix (cost-optimized)

| Agent | Model | Rationale |
|---|---|---|
| Ingestor | none | Pure parsing (LlamaParse is its own API) |
| Researcher | `gemini-2.5-flash` | Summarize web pages into bullets |
| SectorClassifier | `gemini-2.5-flash` | Single-shot classification |
| Planner | `gemini-2.5-pro` | The reasoning core; pre-fed compressed bullets, not raw context |
| Composer (×N parallel) | `gemini-2.5-pro` | Writes the actual slide content per fact |
| ChartDesigner | `gemini-2.5-flash` | Picks chart type, structures series |
| ImageCurator | `gemini-2.5-flash` (text + vision) | Queries Pexels, visually filters candidates |
| Anonymizer | `gemini-2.5-flash` | Scrubs identifying tokens |
| Critic | `gemini-2.5-flash` | Mechanical checks dominate; Flash handles it |
| CitationTracker | none | Pure aggregation |

### Cost-optimization decisions applied

1. **Critic on Flash** (not Pro). Most of its work is mechanical (source_id existence, fuzzy text match, banned-token scan). Flash is sufficient with a tightly structured prompt.
2. **Compressed input to Planner.** Researcher pre-summarizes all docs and web snippets into ~2k tokens of structured bullets. Planner reads this summary, not raw context. Composer still has access to raw facts when filling slides.
3. **Prompt caching** on Planner and Composer system prompts (Gemini context caching). The schema, sector examples, and branding rules are cached.
4. **Single Critic pass, no revision loop.** Critic runs once, emits a `CriticReport`, logs unresolved issues to the trace, but never re-runs Composer. No `revision_count` field, no `slides_needing_revision` set, no conditional edge after Critic. Flow is strictly linear from Critic → CitationTracker.

### Expected per-teaser cost

$0.20–$0.40 on Gemini API. Soft warning at $2, hard abort threshold at $5 (configurable in `config.py`).

---

## 3. Agents

Each agent is a pure function in its own file under `src/kelp_teaser/agents/`. Target ≤200 lines each.

### 3.1 Ingestor

- **Input:** `input_path`, `company_name`
- **Tools:** `tools/pdf_parser.py` (LlamaParse wrapper), `tools/excel_parser.py` (pandas)
- **Behavior:** Walks the input folder. PDFs → LlamaParse. Excel → pandas flatten. MD/TXT → direct read.
- **Output:** `docs: list[IngestedDoc]` where each has `text`, `source_id` (e.g. `doc:annual_report.pdf`), and per-section anchors where parseable.
- **LLM:** none.

### 3.2 Researcher

- **Input:** `company_name`, `docs`
- **Tools:** `tools/web_search.py` (Tavily)
- **Behavior:** Generates targeted Tavily queries (products, customers, certifications, financials, sector trends). Each result becomes a `WebSnippet` with `source_id` (`web:tavily:<url>`). Flash deduplicates and summarizes long pages into ≤500-token snippets. **Also produces a compressed structured bullet summary (~2k tokens total) of docs + snippets for the Planner.**
- **Output:** `web_snippets: list[WebSnippet]`, `planner_brief: str` (compressed bullets)
- **LLM:** Flash, multiple short calls.
- **Failure mode:** If Tavily fails, log and continue with private data only. `planner_brief` is built from docs alone.

### 3.3 SectorClassifier

- **Input:** `planner_brief`
- **Behavior:** Single Flash call. Reads the compressed brief, returns a `Sector` enum value plus a sub-sector free-text tag and a confidence float.
- **Output:** `sector`, `sector_confidence`
- **Sector enum:** `Manufacturing`, `SpecialtyChemicals`, `D2C`, `SaaS`, `Pharma`, `Logistics`, `FinancialServices`, `Consumer`, `Other`.

### 3.4 Planner

- **Input:** `sector`, `planner_brief`, `company_name` (real, used internally only)
- **Behavior:** Pro call. Inputs include sector, the compressed brief, the available `ChartKind` enum, the available `ComponentKind` enum, and the rules of the game (3 slides, blind-by-codename, branding constraints, sector spec examples from the hackathon problem). Outputs a `DeckPlan` (Pydantic).
- **Output:** `plan: DeckPlan` containing a generated `codename` and 3 `SlidePlan`s. Each `SlidePlan` has a `title` and a list of `SectionPlan`s. Each `SectionPlan` has a `kind` (one of `ComponentKind`), `data_hooks` (fact keys referenced from docs/snippets), and optionally a `chart_spec` skeleton or `image_brief`.
- **LLM:** Pro, one call. Prompt-cached system prompt.
- **Validation:** Pydantic enforces exactly 3 slides; each slide has 1–5 sections; section kinds are from the enum.

### 3.5 Composer (parallel fan-out)

- **Input:** one `SlidePlan`, full `docs` + `web_snippets`, `codename`
- **Behavior:** Pro call per slide. Writes the actual slide content: each section's text, each metric's value, each bullet. **Every fact written carries its `source_id` referencing a doc or snippet.** Output is a `ComposedSlide`.
- **Output:** `composed_slides[slide_index] = ComposedSlide`
- **Parallelism:** LangGraph `Send` fans out across the 3 slides. Results fan in via dict-merge.
- **Validation:** Pydantic validator on `ComposedSection` rejects any `Fact` lacking a `source_id`.
- **Sub-calls during composition:**
  - If a section is `kind="chart"` → ChartDesigner produces a `ChartSpec`.
  - If a section is `kind="hero_image"` → ImageCurator produces an image path.

### 3.6 ChartDesigner

- **Input:** `SectionPlan` of kind `chart`, relevant facts
- **Behavior:** Flash call. Picks chart type from the library of 6 (revenue growth bar/line, segment mix donut, margin trend line, geo split stacked bar, channel mix donut, KPI strip). Structures data series, axis labels, units.
- **Output:** `ChartSpec` (consumed downstream by `render/charts.py` which builds native python-pptx charts).

### 3.7 ImageCurator

- **Input:** `SectionPlan` of kind `hero_image`, `image_brief`
- **Tools:** `tools/image_search.py` (Pexels)
- **Behavior:**
  1. Flash generates 2–3 specific Pexels queries from the brief (e.g. "stainless steel reactor vessel pharmaceutical plant interior", not "factory").
  2. Pexels returns candidates.
  3. Flash-vision picks the best, rejects any with visible logos, text overlays, or people-in-corporate-suits (looks stock-cheesy).
- **Output:** local image path under `data/outputs/.../intermediate/images/`, plus license metadata that becomes a citation row.

### 3.8 Anonymizer

- **Input:** all `composed_slides`, `company_name`, `codename`, optional brand-name list from Researcher
- **Behavior:** Flash pass. Scans every `ComposedSlide`'s text. Replaces residual real-name tokens with codename. Rewrites identifying phrases:
  - Exact addresses → regional generalization
  - Founding years → ranges ("over 35 years ago")
  - Unique product/brand names → generic category terms
  - Founder names → "the founding team"
- **Output:** mutates `composed_slides` in place, appends to `anonymization_log: list[Substitution]`.

### 3.9 Critic

- **Input:** `composed_slides`, `docs`, `web_snippets`, `anonymization_log`, `sector`, `plan`
- **Behavior:** Flash call with structured output. Five checks:
  1. **Source validity.** Every claim's `source_id` exists in `docs` or `web_snippets`, and the source text actually contains the claimed number/phrase (fuzzy match — Levenshtein ≥ 0.8 on the numeric/key tokens).
  2. **Anonymization completeness.** No original-name tokens, no unique brand names from the known list, no exact addresses.
  3. **Internal consistency.** Chart values match metric tile values within the same slide (deterministic check, not LLM).
  4. **Length discipline.** Bullets ≤20 words. Deterministic check.
  5. **Sector fit.** Planner's chosen sections suit the classified sector (LLM judgment).
- **Output:** `critic_report: CriticReport` with per-slide `CriticIssue`s.
- **No loop back.** Issues are logged to the trace; flow continues unconditionally.

### 3.10 CitationTracker

- **Input:** `composed_slides`, `docs`, `web_snippets`, image license metadata
- **Behavior:** Pure function, no LLM. Walks all `ComposedSlide`s, collects every `source_id` referenced, builds the structured `CitationTable` (Slide → Claim → Source → Verbatim Quote → Confidence).
- **Output:** `citation_table: CitationTable`

### 3.11 Renderers (not agents, no LLM)

- **`render/deck.py`** consumes `composed_slides[]` + `theme.py` and produces `teaser.pptx`. Uses native python-pptx shapes, text boxes, and charts. Enforces Kelp branding (Dark Indigo primary, pink→orange gradient accent, Cyan accent, Arial Bold headings, Arial Regular body, top "Kelp" logo placeholder, bottom-center "Strictly Private & Confidential" footer at 9pt).
- **`render/citations_doc.py`** consumes `citation_table` and produces `citations.docx` as a real Word table with one row per claim. Pexels image attributions appended at the end.

---

## 4. Shared state and schemas

### 4.1 `GraphState` (Pydantic)

```python
class GraphState(BaseModel):
    # Input
    company_name: str
    input_path: Path
    run_id: str

    # Filled by Ingestor / Researcher
    docs: list[IngestedDoc] = []
    web_snippets: list[WebSnippet] = []
    planner_brief: str = ""

    # Filled by SectorClassifier
    sector: Sector | None = None
    sector_confidence: float | None = None

    # Filled by Planner
    plan: DeckPlan | None = None

    # Filled by Composer (parallel fan-in)
    composed_slides: dict[int, ComposedSlide] = {}

    # Filled by Anonymizer
    anonymization_log: list[Substitution] = []

    # Filled by Critic
    critic_report: CriticReport | None = None

    # Filled by CitationTracker
    citation_table: CitationTable | None = None

    # Output paths
    pptx_path: Path | None = None
    citations_path: Path | None = None
    trace_path: Path | None = None
```

### 4.2 Schema modules (`src/kelp_teaser/schemas/`)

- **`facts.py`** — `SourceRef`, `Fact` (value + source_id + verbatim_quote), `IngestedDoc`, `WebSnippet`
- **`plan.py`** — `Sector` enum, `ChartKind` enum, `ComponentKind` enum, `SectionPlan`, `SlidePlan`, `DeckPlan`
- **`slide.py`** — `ComposedSlide`, `ComposedSection`, `ChartSpec`, `MetricTile`, `Bullet`
- **`critic.py`** — `CriticIssue`, `CriticReport`, `Substitution`
- **`citations.py`** — `CitationRow`, `CitationTable`

**Critical invariant:** every textual claim inside a `ComposedSlide` is a `Fact`, not a raw string. A Pydantic validator on `ComposedSection` rejects any `Fact` lacking a non-empty `source_id`. This is what makes citation integrity and Critic source-validation possible without re-prompting.

### 4.3 `source_id` format

- `doc:<filename>#<page_or_section>` — e.g. `doc:annual_report.pdf#p12`
- `web:<provider>:<url>` — e.g. `web:tavily:https://companywebsite.com/about`
- `image:pexels:<photo_id>` — for image attribution rows in citations doc

---

## 5. Prompts

Prompts live as Jinja2-templated Markdown files under `prompts/`, loaded at startup via a `Prompt` class exposing `.render(**vars)`. Putting prompts in files (not Python) means iteration without code changes and clean git diffs.

Files:
- `prompts/sector_classifier.md`
- `prompts/planner.md` — the longest; includes 3-slide rule, blind-teaser rules, branding constraints, sector spec examples from the hackathon problem (Manufacturing/SpecialtyChemicals example, D2C example)
- `prompts/composer.md`
- `prompts/chart_designer.md`
- `prompts/image_curator.md`
- `prompts/anonymizer.md`
- `prompts/critic.md`

---

## 6. Folder structure

```
AI-ML-GC-RND/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── src/kelp_teaser/
│   ├── __init__.py
│   ├── config.py               # paths, model names, branding constants, cost guardrails
│   ├── cli.py                  # entrypoint (replaces main.py)
│   │
│   ├── graph/
│   │   ├── state.py
│   │   └── build_graph.py
│   │
│   ├── agents/
│   │   ├── ingestor.py
│   │   ├── researcher.py
│   │   ├── sector_classifier.py
│   │   ├── planner.py
│   │   ├── composer.py
│   │   ├── chart_designer.py
│   │   ├── image_curator.py
│   │   ├── anonymizer.py
│   │   ├── critic.py
│   │   └── citation_tracker.py
│   │
│   ├── tools/
│   │   ├── pdf_parser.py
│   │   ├── excel_parser.py
│   │   ├── web_search.py
│   │   ├── image_search.py
│   │   └── llm.py              # Gemini client (Flash + Pro), prompt-cache helpers, cost tracking
│   │
│   ├── render/
│   │   ├── deck.py
│   │   ├── slide_components.py # reusable: metric tile, quadrant, grid, hero
│   │   ├── charts.py           # 6 chart types
│   │   ├── theme.py            # Kelp branding constants
│   │   └── citations_doc.py
│   │
│   └── schemas/
│       ├── facts.py
│       ├── plan.py
│       ├── slide.py
│       ├── critic.py
│       └── citations.py
│
├── prompts/                    # Jinja2-templated .md files
│   ├── sector_classifier.md
│   ├── planner.md
│   ├── composer.md
│   ├── chart_designer.md
│   ├── image_curator.md
│   ├── anonymizer.md
│   └── critic.md
│
├── data/
│   ├── inputs/                 # data packs (one folder per company)
│   └── outputs/{company}_{run_id}/
│       ├── teaser.pptx
│       ├── citations.docx
│       ├── trace.json
│       └── intermediate/
│
├── tests/
│   ├── unit/
│   └── fixtures/
│
└── docs/
    └── superpowers/specs/
```

---

## 7. Error handling, observability, and cost guardrails

- **Boundary validation only.** Pydantic validates external LLM output and parsed files. Internal calls trust their types.
- **Fail-soft per agent, fail-hard per pipeline.** If Tavily fails, log and continue with private data only. If Planner returns invalid JSON, retry once with a structured-output reminder, then hard fail with the trace saved.
- **No silent N/A.** If a slide section can't be filled (data missing), the Planner is responsible for not including that section. Composer never emits "N/A" — better to swap component than fake data.
- **Trace everything.** Each agent writes `intermediate/{step:02d}_{agent}.json`. Top-level `trace.json` records per-step timing, model ID, input/output token counts, and an estimated cost (rupees and dollars).
- **No retry storms.** Each LLM call: max 2 attempts.
- **Cost guardrails.** Per-run cost estimate printed at end. Soft warning if a run exceeds $2; hard abort threshold $5 (configurable in `config.py`) to prevent runaway loops.

---

## 8. Testing

- **Unit tests** (`tests/unit/`) — pure functions only: prompt rendering, Pydantic validators, `source_id` parsing, anonymizer regex helpers, `ChartSpec` → python-pptx mapping. Fast, deterministic, no API calls.
- **Schema tests** — fixture JSONs (captured from real Gemini runs) must round-trip through every Pydantic model. Catches schema drift.
- **Render tests** — given a fixture `ComposedSlide[]`, render the `.pptx` and assert it opens, has the right slide count, and contains expected text. No visual quality assertion.
- **End-to-end smoke test** — one cheap company (Ksolves) runs the full graph with `MODEL_FAST` overriding all agents, asserts artifacts exist and trace is well-formed. Run manually before commits.
- **No LLM mocking in unit suite.** LLM-touching code is exercised by the smoke test only.

---

## 9. Migration plan

1. Create `src/kelp_teaser/` alongside existing scripts. Old code keeps working during migration.
2. Move inputs: `examples/*` → `data/inputs/*` (one folder per company).
3. Archive or delete stale root-level `*_ANALYSIS.json` and `*_FULL_CONTEXT.txt` files.
4. Archive `Final_Submissions/*`.
5. Port `ingest.py` logic into `tools/pdf_parser.py` + `tools/excel_parser.py` + `agents/ingestor.py`. Reuse LlamaParse and Tavily wiring.
6. Port `ppt_engine.py`'s working primitives (TextStyler, shape helpers, theme colors) into `render/slide_components.py` + `render/theme.py`. Discard the hardcoded slide layouts.
7. Port `utils.py` Pexels logic into `tools/image_search.py`.
8. Build agents one by one, validating each on Ksolves fixture data.
9. Wire LangGraph in `graph/build_graph.py`.
10. Delete old root-level `.py` scripts once the new CLI works end-to-end on at least 2 companies.

---

## 10. What changes from the v1 hackathon code

- **Removed:** monolithic `analyze.py` prompt, fixed 4-slide layout in `ppt_engine.py`, `main.py` numeric menu, hardcoded paths, root-level outputs, duplicate Gati files.
- **Kept:** LlamaParse, Tavily, Pexels integrations; python-pptx as renderer; Gemini as runtime LLM; the principle of "code, not templates."
- **Reshaped:** prompts move to files; slides become dynamic; JSON schemas become Pydantic; outputs become per-run folders; citations become structured with per-claim source_ids.
