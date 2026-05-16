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
