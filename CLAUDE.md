# CLAUDE.md — Kelp Teaser v2

This file is the orientation brief for any future Claude session working on this project. Read it first.

## What this project is

An agentic pipeline that converts a company "data pack" (PDFs / Excel / Markdown) into a blind 3-slide M&A investment teaser (`.pptx`) plus a structured citations document (`.docx`). Originally built for the Kelp "Automated Deal Flow" hackathon (Jan 2026); now being revamped into a portfolio-grade artifact.

The v2 architecture is documented in [docs/superpowers/specs/2026-05-16-agentic-teaser-pipeline-design.md](docs/superpowers/specs/2026-05-16-agentic-teaser-pipeline-design.md). Read it before making architectural decisions.

## Current status

| Phase | Status | Branch / Tag | Tests |
|---|---|---|---|
| **Phase A — Foundation** (schemas, tools, renderers, theme, prompt loader scaffold) | Merged to `main` at `f7116f9` | `phase-a-foundation` (history only) | 61 ✓ |
| **Phase B — Agents + LangGraph + CLI** (9 agents, parallel Composer fan-out, cost guardrails, v1 deletion) | Merged to `main` at `8e0ae16` | `phase-b-agents` (history only) | 101 ✓ |
| **Phase C — Live API + polish** (this is what's next) | Not started | TBD | — |

The branch this session lives on is **`main`**. `main` is local-only ahead of `origin/main` (Phase A+B is unpushed). Don't push without explicit user instruction.

## How to work in this repo

### Install
```bash
python -m venv venv && source venv/Scripts/activate    # Windows bash
pip install -e ".[dev]"
cp .env.example .env  # populate API keys when you need them
```

### Run tests
```bash
pytest -v
```
Expect **101 passed** (Phase B baseline). No live API calls happen during tests — `tests/fixtures/stub_llm.py` monkeypatches `complete_text`/`complete_json` with canned responses.

### Run the pipeline (real Gemini API)
```bash
kelp-teaser run data/inputs/Ksolves/
```
Outputs land at `data/outputs/<company>_<run_id>/teaser.pptx`, `citations.docx`, `trace.json`. Don't run this without `.env` configured. Cost: ~$0.20–0.40 per run on real Gemini.

### Folder layout
```
src/kelp_teaser/
├── config.py               # paths, model IDs, cost thresholds
├── cli.py                  # entrypoint (`kelp-teaser run …`)
├── graph/                  # LangGraph state + topology + trace writer
│   ├── state.py            # GraphState (Pydantic)
│   ├── build_graph.py      # node wiring, parallel fan-out via Send
│   ├── nodes.py            # bind_node adapter
│   └── trace.py            # per-step JSON + run-level trace.json
├── agents/                 # 9 agents, one file each, ≤200 lines
│   ├── ingestor.py
│   ├── researcher.py       # Tavily + Flash summarize + planner_brief
│   ├── sector_classifier.py
│   ├── planner.py          # Pro; outputs DeckPlan with codename + 3 slides
│   ├── composer.py         # Pro; one call per slide, called in parallel
│   ├── chart_designer.py   # Flash; called by Composer for chart sections
│   ├── image_curator.py    # Flash + Pexels; called by Composer for hero_image sections
│   ├── anonymizer.py       # Flash, selective; literal-swap fallback
│   ├── critic.py           # Flash judgment + deterministic checks
│   └── citation_tracker.py # pure aggregation, no LLM
├── tools/                  # external integrations
│   ├── llm.py              # Gemini client (google-genai SDK), CostTracker, guardrails
│   ├── prompt_loader.py    # Jinja2-templated .md files from prompts/
│   ├── pdf_parser.py       # LlamaParse
│   ├── excel_parser.py     # pandas
│   ├── web_search.py       # Tavily
│   └── image_search.py     # Pexels
├── render/                 # python-pptx + python-docx, no LLM
│   ├── theme.py            # Kelp branding constants
│   ├── slide_components.py # header/footer/container/tile/bullets primitives
│   ├── charts.py           # 6 chart kinds → native python-pptx
│   ├── deck.py             # composes ComposedSlide[] → .pptx
│   └── citations_doc.py    # CitationTable → 6-column .docx
└── schemas/                # Pydantic models, enforce all contracts
    ├── facts.py            # SourceRef, Fact, IngestedDoc, WebSnippet
    ├── plan.py             # Sector, ChartKind, ComponentKind, SectionPlan, SlidePlan, DeckPlan
    ├── slide.py            # Bullet, MetricTile, ChartSpec, ComposedSection, ComposedSlide
    ├── critic.py           # CriticIssue, CriticReport, Substitution
    └── citations.py        # CitationRow, CitationTable

prompts/                    # 7 Jinja2-templated .md files (NOT in Python)
data/inputs/<Company>/      # one folder per test company (6 onepagers shipped)
data/outputs/               # per-run artifacts; gitignored
docs/superpowers/specs/     # the design doc (source of architectural truth)
docs/superpowers/plans/     # Phase A and Phase B implementation plans
archive/v1/                 # old code preserved for reference
tests/unit/                 # 101 tests; no LLM calls
tests/fixtures/
├── ksolves_data_pack/      # minimal fixture used by the end-to-end smoke test
└── stub_llm.py             # patch_llm(monkeypatch, …) helper
```

## Key invariants to preserve

These are load-bearing. Don't break them:

1. **Every textual claim on a slide carries a `source_id`.** Pydantic validators on `Bullet`, `MetricTile`, `ChartSpec`, `HeroImage` reject empty `source_id`. The Critic checks the id exists in `docs ∪ web_snippets`.
2. **Real company name never appears in the rendered deck.** Anonymizer scrubs; Critic spot-checks. Anonymization uses the codename from `DeckPlan.codename`.
3. **Exactly 3 slides.** `DeckPlan` enforces `min_length=3, max_length=3`. The Composer fans out into exactly 3 parallel calls.
4. **CostTracker is thread-safe.** It has an internal lock; Composer fan-out is parallel. Don't add code paths that mutate `calls`/`by_model` without acquiring `_lock`.
5. **All LLM calls go through `tools/llm.py`** (`complete_text` or `complete_json`). The `CURRENT_TRACKER` module-level fallback only works if agents use these helpers.
6. **Prompts live in `prompts/*.md`, not in Python.** Iterate prompts without code changes.

## Conventions

- **Test discipline.** Every new agent or tool ships with unit tests in `tests/unit/`. LLM calls in tests are stubbed via `tests.fixtures.stub_llm.patch_llm()`. We do not mock python-pptx or pandas internals; tests build real `.pptx` files into `tmp_path` and assert on the output.
- **Agent signature.** Every agent exposes `run(state: GraphState, *, trace_writer: TraceWriter | None = None) -> dict`. The dict is merged into state by LangGraph.
- **Pure-function bias.** Agents return dicts, do not mutate state. Renderers consume final state and produce files; no LLM.
- **Fail-soft at boundaries.** Tavily / Pexels / LlamaParse all return empty values on failure (logged). LLM calls retry up to `LLM_MAX_ATTEMPTS` (2) and then raise.
- **Commits.** One logical change per commit. Real commit messages, not "WIP". Always include `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` when committing code Claude wrote.
- **Workflow.** Significant work uses the `superpowers:*` skills: brainstorming → writing-plans → subagent-driven-development. For small changes, just do them.

## Known polish items (deferred from Phase B final review)

These are flagged in memory ([phase_c_polish_items.md](../../.claude/projects/c--Users-Rishabh-Kumar-PPT-Hackathon-AI-ML-GC-RND/memory/phase_c_polish_items.md)) and should be addressed in Phase C:

1. `agents/critic.py` lines 98-102 — on LLM judgment failure, append a synthetic "judgment_unavailable" issue rather than silently returning `[]`.
2. `cli.py` — call `trace.add_cost(tracker.total_cost_usd)` before `trace.finalize()`; the trace file currently always reports cost 0.
3. `agents/researcher.py` — log a warning when Tavily returns zero hits across all queries.
4. `agents/composer.py` lines 76-94 — Composer sub-call failures (ChartDesigner / ImageCurator) currently log silently; consider Critic-visible warnings when a planned chart/image is missing.
5. `render/deck.py` — assert slide indices are contiguous 0..N-1.

## What NOT to do

- Don't push to `origin/main` without explicit user instruction.
- Don't introduce a v3 idea (revision loop, RAG, vision filter, multi-provider fallback, etc.) without checking the spec's Section 11 "Deferred to v3" first — many ideas are intentionally out of scope for cost reasons.
- Don't bypass `tools/llm.py` for LLM calls.
- Don't put prompts in Python code.
- Don't add features when the user asked for a fix.
