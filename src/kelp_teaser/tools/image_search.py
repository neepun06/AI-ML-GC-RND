"""Pexels image search wrapper."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import requests

from kelp_teaser.config import PEXELS_API_KEY

log = logging.getLogger(__name__)


@dataclass
class PexelsCandidate:
    photo_id: int
    src_large: str
    photographer: str
    photographer_url: str
    alt: str


def build_pexels_query_url(query: str, *, orientation: str = "landscape", per_page: int = 5) -> str:
    params = {"query": query, "orientation": orientation, "per_page": per_page}
    return f"https://api.pexels.com/v1/search?{urlencode(params)}"


def search_pexels(query: str, *, per_page: int = 5) -> list[PexelsCandidate]:
    if not PEXELS_API_KEY:
        log.warning("PEXELS_API_KEY not set; image search disabled")
        return []
    try:
        url = build_pexels_query_url(query, per_page=per_page)
        resp = requests.get(url, headers={"Authorization": PEXELS_API_KEY}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [
            PexelsCandidate(
                photo_id=p.get("id", 0),
                src_large=p.get("src", {}).get("large", ""),
                photographer=p.get("photographer", ""),
                photographer_url=p.get("photographer_url", ""),
                alt=p.get("alt", ""),
            )
            for p in data.get("photos", [])
        ]
    except Exception as e:  # noqa: BLE001
        log.error("Pexels search failed for %r: %s", query, e)
        return []


def download_image(url: str, dest: Path) -> bool:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Image download failed (%s -> %s): %s", url, dest, e)
        return False
