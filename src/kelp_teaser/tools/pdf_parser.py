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
