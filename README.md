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
pip install -e “.[dev]”
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












