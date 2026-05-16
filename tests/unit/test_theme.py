from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from kelp_teaser.render import theme


def test_palette_has_required_keys():
    for k in ("primary", "accent", "accent_gradient_end", "cyan", "bg_slide",
              "white", "text_dark", "text_muted", "border_light"):
        assert k in theme.PALETTE
        assert isinstance(theme.PALETTE[k], RGBColor)


def test_slide_dimensions_widescreen():
    assert theme.SLIDE_W == Inches(13.333)
    assert theme.SLIDE_H == Inches(7.5)


def test_footer_text_matches_brand_guidelines():
    assert theme.FOOTER_TEXT == "Strictly Private & Confidential – Prepared by Kelp M&A Team"
    assert theme.FOOTER_FONT_SIZE == Pt(9)


def test_heading_font_is_arial_bold():
    assert theme.HEADING_FONT == "Arial"
    assert theme.BODY_FONT == "Arial"
