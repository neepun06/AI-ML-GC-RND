import json
from pathlib import Path

from kelp_teaser.graph.trace import TraceWriter


def test_trace_writer_writes_step_files(tmp_path):
    writer = TraceWriter(run_dir=tmp_path)
    writer.write_step("ingestor", {"docs_count": 3})
    writer.write_step("researcher", {"snippets_count": 7})

    files = sorted((tmp_path / "intermediate").glob("*.json"))
    assert len(files) == 2
    assert files[0].name == "00_ingestor.json"
    assert files[1].name == "01_researcher.json"

    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["agent"] == "ingestor"
    assert payload["data"] == {"docs_count": 3}


def test_trace_writer_finalize_writes_summary(tmp_path):
    writer = TraceWriter(run_dir=tmp_path)
    writer.write_step("ingestor", {"docs_count": 3})
    writer.write_step("researcher", {"snippets_count": 7})
    writer.add_cost(0.05)
    writer.add_cost(0.12)
    writer.finalize()

    trace = json.loads((tmp_path / "trace.json").read_text(encoding="utf-8"))
    assert trace["total_cost_usd"] == 0.17
    assert len(trace["steps"]) == 2
    assert trace["steps"][0]["agent"] == "ingestor"


def test_trace_writer_no_op_when_no_run_dir():
    writer = TraceWriter(run_dir=None)
    writer.write_step("anything", {"x": 1})
    writer.add_cost(0.1)
    writer.finalize()  # must not raise
