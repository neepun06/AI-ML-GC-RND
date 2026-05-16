from pathlib import Path

from kelp_teaser.agents.ingestor import run as run_ingestor
from kelp_teaser.graph.state import GraphState

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ksolves_data_pack"


def _state(input_path: Path) -> GraphState:
    return GraphState(company_name="Ksolves", input_path=input_path, run_id="t1")


def test_ingestor_reads_markdown_file():
    state = _state(FIXTURE)
    result = run_ingestor(state)
    docs = result["docs"]
    assert len(docs) == 1
    assert docs[0].filename == "Ksolves-OnePager.md"
    assert docs[0].source_id == "doc:Ksolves-OnePager.md"
    assert "Ksolves is a mid-cap IT services" in docs[0].text


def test_ingestor_skips_hidden_and_unknown_files(tmp_path):
    (tmp_path / ".hidden.md").write_text("ignore me")
    (tmp_path / "good.md").write_text("read me")
    (tmp_path / "unknown.xyz").write_text("skip me")
    state = _state(tmp_path)
    result = run_ingestor(state)
    filenames = sorted(d.filename for d in result["docs"])
    assert filenames == ["good.md"]


def test_ingestor_accepts_single_file_path(tmp_path):
    p = tmp_path / "solo.md"
    p.write_text("solo content")
    state = _state(p)
    result = run_ingestor(state)
    assert len(result["docs"]) == 1
    assert result["docs"][0].filename == "solo.md"


def test_ingestor_returns_empty_docs_when_folder_empty(tmp_path):
    state = _state(tmp_path)
    result = run_ingestor(state)
    assert result["docs"] == []
