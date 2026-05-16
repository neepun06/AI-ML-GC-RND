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
