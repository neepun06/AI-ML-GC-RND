from pptx import Presentation

from kelp_teaser.render.deck import render_deck
from tests.fixtures.ksolves_minimal import three_slides


def test_render_deck_writes_three_slides(tmp_path):
    out = tmp_path / "teaser.pptx"
    render_deck(slides=three_slides(), codename="Project Halo", out_path=out)
    assert out.exists()
    prs = Presentation(str(out))
    assert len(prs.slides) == 3


def test_render_deck_includes_footer_text_on_every_slide(tmp_path):
    out = tmp_path / "teaser.pptx"
    render_deck(slides=three_slides(), codename="Project Halo", out_path=out)
    prs = Presentation(str(out))
    from kelp_teaser.render import theme
    for s in prs.slides:
        texts = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame]
        assert any(theme.FOOTER_TEXT in t for t in texts)


def test_render_deck_uses_codename_in_header(tmp_path):
    out = tmp_path / "teaser.pptx"
    render_deck(slides=three_slides(), codename="Project Halo", out_path=out)
    prs = Presentation(str(out))
    first = prs.slides[0]
    texts = [sh.text_frame.text for sh in first.shapes if sh.has_text_frame]
    assert any("Project Halo" in t for t in texts)
