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

# Model IDs. MODEL_SMART can be overridden via KELP_MODEL_SMART env var
# (e.g. to point Planner/Composer at Flash for free-tier smoke runs, since
# gemini-2.5-pro has zero free-tier quota as of 2026).
MODEL_FAST = "gemini-2.5-flash"
MODEL_SMART = os.getenv("KELP_MODEL_SMART", "gemini-2.5-pro")

# Cost guardrails (USD)
COST_SOFT_WARNING = 2.00
COST_HARD_ABORT = 5.00

# Retry policy. Retries feed the specific validation errors back to the model
# (see tools/llm.complete_json), so a third attempt meaningfully improves
# recovery from transient schema violations.
LLM_MAX_ATTEMPTS = 3

# Parallel composer fan-out cap
MAX_PARALLEL_SLIDES = 3

# Web search budget per Tavily query. Each hit triggers a Flash summarize
# call, so 3 queries × N hits = up to 3N extra Flash calls per run. Default
# is 1 so a fully-integrated run fits comfortably in free-tier Flash quota.
# Bump up to 3 on paid tier for richer Planner briefs.
WEB_SEARCH_MAX_RESULTS = int(os.getenv("KELP_WEB_SEARCH_MAX_RESULTS", "1"))
