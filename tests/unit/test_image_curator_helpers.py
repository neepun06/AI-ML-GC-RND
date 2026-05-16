from pathlib import Path

from kelp_teaser.agents.image_curator import (
    ImageQueries,
    curate_image,
)
from kelp_teaser.schemas.plan import ComponentKind, SectionPlan
from kelp_teaser.schemas.slide import HeroImage
from kelp_teaser.tools.image_search import PexelsCandidate
from tests.fixtures.stub_llm import patch_llm


def _section() -> SectionPlan:
    return SectionPlan(
        kind=ComponentKind.hero_image,
        image_brief="pharmaceutical reactor vessel interior",
        data_hooks=[],
    )


def test_curate_image_returns_none_when_no_candidates(monkeypatch, tmp_path):
    patch_llm(monkeypatch, json_responses=[
        ImageQueries(queries=["pharma reactor", "lab equipment"]),
    ])
    monkeypatch.setattr(
        "kelp_teaser.agents.image_curator.image_search.search_pexels",
        lambda q, per_page=5: [],
    )
    result = curate_image(_section(), sector="Pharma", out_dir=tmp_path)
    assert result is None


def test_curate_image_downloads_first_candidate(monkeypatch, tmp_path):
    candidates = [
        PexelsCandidate(photo_id=42, src_large="https://images.pexels.com/x.jpg",
                        photographer="Jane", photographer_url="https://pexels.com/jane",
                        alt="reactor"),
    ]
    patch_llm(monkeypatch, json_responses=[
        ImageQueries(queries=["pharma reactor"]),
    ])
    monkeypatch.setattr(
        "kelp_teaser.agents.image_curator.image_search.search_pexels",
        lambda q, per_page=5: candidates,
    )
    dl_calls = []
    def fake_download(url, dest):
        dl_calls.append((url, dest))
        Path(dest).write_bytes(b"fake-png")
        return True
    monkeypatch.setattr(
        "kelp_teaser.agents.image_curator.image_search.download_image",
        fake_download,
    )
    result = curate_image(_section(), sector="Pharma", out_dir=tmp_path)
    assert isinstance(result, HeroImage)
    assert result.source_id == "image:pexels:42"
    assert Path(result.path).exists()
    assert dl_calls[0][0] == "https://images.pexels.com/x.jpg"
