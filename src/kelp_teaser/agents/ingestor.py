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
