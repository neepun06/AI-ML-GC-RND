"""ImageCurator: Flash generates Pexels queries; we download the top candidate.

A future v3 enhancement is a Flash-vision filter on the downloaded image to reject
logos/text/people-in-suits. Phase B keeps it simple: take the first candidate.
"""
from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from kelp_teaser.config import MODEL_FAST
from kelp_teaser.schemas.plan import SectionPlan
from kelp_teaser.schemas.slide import HeroImage
from kelp_teaser.tools import image_search, llm
from kelp_teaser.tools.prompt_loader import load_prompt

log = logging.getLogger(__name__)


class ImageQueries(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=4)


def curate_image(section: SectionPlan, *, sector: str, out_dir: Path) -> HeroImage | None:
    if not section.image_brief:
        return None

    prompt = load_prompt("image_curator").render(
        image_brief=section.image_brief, sector=sector,
    )
    try:
        plan = llm.complete_json(MODEL_FAST, prompt, ImageQueries)
    except Exception as e:  # noqa: BLE001
        log.error("ImageCurator query gen failed: %s", e)
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    for query in plan.queries:
        candidates = image_search.search_pexels(query, per_page=3)
        for candidate in candidates:
            if not candidate.src_large:
                continue
            dest = out_dir / f"pexels_{candidate.photo_id}.jpg"
            if image_search.download_image(candidate.src_large, dest):
                return HeroImage(
                    path=str(dest),
                    alt_text=candidate.alt or section.image_brief,
                    source_id=f"image:pexels:{candidate.photo_id}",
                )
    return None
