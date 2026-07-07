"""Render a list of ComposedSlide objects into a .pptx file.

The renderer is dumb on purpose: it only knows how to draw what each
ComposedSection says. All content decisions happen upstream in the agents.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from kelp_teaser.render import theme
from kelp_teaser.render.charts import render_chart
from kelp_teaser.render.slide_components import (
    add_footer,
    add_header,
    draw_bullet_list,
    draw_container,
    draw_metric_tile,
)
from kelp_teaser.schemas.plan import ComponentKind
from kelp_teaser.schemas.slide import ComposedSection, ComposedSlide


def render_deck(*, slides: list[ComposedSlide], codename: str, out_path: Path) -> Path:
    """Render the deck. Returns the saved path."""
    indices = [s.index for s in slides]
    assert sorted(indices) == list(range(len(slides))), (
        f"Slide indices must be contiguous 0..{len(slides) - 1}, "
        f"got {sorted(indices)}"
    )

    prs = Presentation()
    prs.slide_width = theme.SLIDE_W
    prs.slide_height = theme.SLIDE_H

    for composed in sorted(slides, key=lambda s: s.index):
        _render_slide(prs, composed, codename)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return out_path


def _render_slide(prs, composed: ComposedSlide, codename: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = theme.PALETTE["bg_slide"]

    add_header(slide, codename=codename, subtitle=composed.title)
    add_footer(slide)

    # Below the header, place sections top-to-bottom in equal rows.
    n = len(composed.sections)
    row_h = (theme.SLIDE_H - theme.HEADER_HEIGHT - Inches(0.6)) / max(n, 1)
    y_cursor = theme.HEADER_HEIGHT + Inches(0.2)

    for section in composed.sections:
        _render_section(slide, section,
                        x=theme.MARGIN, y=y_cursor,
                        w=theme.CONTENT_W, h=row_h - Inches(0.1))
        y_cursor += row_h


def _render_section(slide, section: ComposedSection, *, x, y, w, h) -> None:
    if section.kind == ComponentKind.bullet_list:
        draw_container(slide, x, y, w, h, title=section.heading)
        draw_bullet_list(slide, x, y + Inches(0.4), w, h - Inches(0.4), section.bullets)

    elif section.kind == ComponentKind.metric_tile:
        # Equal horizontal split across N tiles.
        n = max(len(section.metrics), 1)
        tile_w = (w - (n - 1) * theme.GUTTER) / n
        cx = x
        for tile in section.metrics:
            draw_metric_tile(slide, cx, y, tile_w, h, tile)
            cx += tile_w + theme.GUTTER

    elif section.kind == ComponentKind.chart and section.chart is not None:
        draw_container(slide, x, y, w, h, title=section.heading)
        render_chart(slide,
                     x + Inches(0.2), y + Inches(0.5),
                     w - Inches(0.4), h - Inches(0.6),
                     section.chart)

    elif section.kind == ComponentKind.hero_image and section.image is not None:
        # If the image file actually exists on disk, render it. Otherwise
        # (Composer hallucinated a path, or ImageCurator was skipped because
        # PEXELS_API_KEY is not set) fail soft to a labelled placeholder so
        # the deck still renders.
        image_path = Path(section.image.path)
        if image_path.is_file():
            slide.shapes.add_picture(str(image_path), x, y, width=w, height=h)
        else:
            placeholder_title = (section.heading or section.image.alt_text
                                 or "Image unavailable")
            draw_container(slide, x, y, w, h, title=placeholder_title)

    elif section.kind == ComponentKind.product_grid:
        draw_container(slide, x, y, w, h, title=section.heading or "Portfolio")
        draw_bullet_list(slide, x, y + Inches(0.4), w, h - Inches(0.4), section.bullets)

    elif section.kind == ComponentKind.kpi_strip:
        # Render as horizontal metric tiles (alias of metric_tile layout).
        n = max(len(section.metrics), 1)
        tile_w = (w - (n - 1) * theme.GUTTER) / n
        cx = x
        for tile in section.metrics:
            draw_metric_tile(slide, cx, y, tile_w, h, tile)
            cx += tile_w + theme.GUTTER

    elif section.kind == ComponentKind.quadrant:
        # 2×2 bullet quadrants. Caller must pass 4 bullets to fill all quadrants.
        draw_container(slide, x, y, w, h, title=section.heading)
        half_w = (w - theme.GUTTER) / 2
        half_h = (h - theme.GUTTER - Inches(0.4)) / 2
        cy0 = y + Inches(0.4)
        positions = [
            (x, cy0),
            (x + half_w + theme.GUTTER, cy0),
            (x, cy0 + half_h + theme.GUTTER),
            (x + half_w + theme.GUTTER, cy0 + half_h + theme.GUTTER),
        ]
        for (px, py), bullet in zip(positions, section.bullets[:4]):
            draw_bullet_list(slide, px, py, half_w, half_h, [bullet])
