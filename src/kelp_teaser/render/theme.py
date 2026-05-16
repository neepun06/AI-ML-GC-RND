"""Kelp branding constants — colors, fonts, dimensions, footer text.

Source of truth for everything visual. Renderers MUST NOT define their own
colors or fonts; they pull from here.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

PALETTE: dict[str, RGBColor] = {
    "primary": RGBColor(40, 0, 80),            # Dark Indigo / Violet
    "accent": RGBColor(255, 100, 80),          # Pink → Orange gradient start
    "accent_gradient_end": RGBColor(255, 160, 60),  # Pink → Orange gradient end
    "cyan": RGBColor(50, 180, 230),            # Cyan Blue (icons)
    "bg_slide": RGBColor(255, 255, 255),       # Clean white content background
    "white": RGBColor(255, 255, 255),
    "text_dark": RGBColor(45, 45, 55),
    "text_muted": RGBColor(100, 100, 110),
    "border_light": RGBColor(220, 220, 230),
}

# Slide dimensions (widescreen 16:9)
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

# Page margins and layout
MARGIN = Inches(0.5)
GUTTER = Inches(0.3)
CONTENT_W = SLIDE_W - (MARGIN * 2)
COL2_W = (CONTENT_W - GUTTER) / 2
COL3_W = (CONTENT_W - GUTTER * 2) / 3

# Typography
HEADING_FONT = "Arial"
BODY_FONT = "Arial"
HEADING_SIZE = Pt(24)
SUBHEADING_SIZE = Pt(14)
BODY_SIZE = Pt(11)
CAPTION_SIZE = Pt(9)

# Footer
FOOTER_TEXT = "Strictly Private & Confidential – Prepared by Kelp M&A Team"
FOOTER_FONT_SIZE = Pt(9)

# Header
HEADER_HEIGHT = Inches(1.3)
LOGO_PLACEHOLDER_TEXT = "Kelp"
