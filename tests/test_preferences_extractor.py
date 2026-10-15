from pathlib import Path

import pytest
from pptx import Presentation
from pptx.dml.color import MSO_THEME_COLOR, RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from pdf2deck.preferences import load_preferences
from pdf2deck.schemas import (
    DeckOutline,
    Fonts,
    Palette,
    SlidePlan,
    SlideSize,
    StyledSlide,
    StylePreferences,
    TypeScale,
)
from pdf2deck.services.pptx_service import PptxService
from pdf2deck.services.preferences_extractor import PreferencesExtractor

# Colours and fonts of the theme in python-pptx's bundled default template.
OFFICE_ACCENT_1 = "#4F81BD"
OFFICE_ACCENT_2 = "#C0504D"
OFFICE_FONT = "Calibri"


def _deck(tmp_path: Path, accent: MSO_THEME_COLOR | None = None, name: str = "My Brand 2026") -> Path:
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.625)
    for _ in range(3):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        frame = slide.shapes.add_textbox(0, 0, Inches(8), Inches(1)).text_frame
        title = frame.paragraphs[0].add_run()
        title.text = "A title"
        title.font.size = Pt(28)
        for _ in range(3):
            body = frame.add_paragraph().add_run()
            body.text = "Body text"
            body.font.size = Pt(14)
            if accent is not None:
                body.font.color.theme_color = accent
    path = tmp_path / f"{name}.pptx"
    prs.save(path)
    return path


def test_reads_size_fonts_and_type_scale(tmp_path: Path):
    style = PreferencesExtractor().extract(_deck(tmp_path))

    assert style.name == "my-brand-2026"
    assert (style.slide_size.width_in, style.slide_size.height_in) == (10, 5.62)
    assert (style.fonts.heading, style.fonts.body) == (OFFICE_FONT, OFFICE_FONT)
    assert (style.type_scale.title_pt, style.type_scale.body_pt) == (28, 14)
    assert style.density == "sparse"


def test_palette_defaults_to_theme_order(tmp_path: Path):
    colors = PreferencesExtractor().extract(_deck(tmp_path)).colors

    assert (colors.main, colors.highlight) == (OFFICE_ACCENT_1, OFFICE_ACCENT_2)
    assert (colors.text, colors.background) == ("#000000", "#FFFFFF")


def test_the_accent_the_slides_use_most_becomes_the_main_color(tmp_path: Path):
    colors = PreferencesExtractor().extract(_deck(tmp_path, MSO_THEME_COLOR.ACCENT_2)).colors

    # The slides use no other brand colour, so the highlight is not a stock theme accent.
    assert (colors.main, colors.highlight) == (OFFICE_ACCENT_2, OFFICE_ACCENT_2)
    assert colors.text == "#000000"


def test_colours_and_fonts_set_on_the_slides_win_over_the_theme(tmp_path: Path):
    prs = Presentation()
    for _ in range(2):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor.from_string("F8FAFC")
        # Autoshapes carry a <p:style> naming accent1, which must not count as a use.
        for fill in ("059669", "059669", "F0FDF4"):
            shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(1), Inches(1))
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor.from_string(fill)
        frame = slide.shapes.add_textbox(0, 0, Inches(8), Inches(1)).text_frame
        for text, size, color, font in [
            ("A title", 28, "0F172A", "Space Grotesk"),
            ("Body text", 14, "475569", "Plus Jakarta Sans"),
            ("Body text", 14, "475569", "Plus Jakarta Sans"),
            ("Label", 14, "F59E0B", "Plus Jakarta Sans"),
        ]:
            run = frame.add_paragraph().add_run()
            run.text = text
            run.font.size = Pt(size)
            run.font.name = font
            run.font.color.rgb = RGBColor.from_string(color)
    path = tmp_path / "direct.pptx"
    prs.save(path)

    style = PreferencesExtractor().extract(path)

    assert style.colors.model_dump() == {
        "main": "#059669", "highlight": "#F59E0B", "text": "#475569", "background": "#F8FAFC",
    }
    assert (style.fonts.heading, style.fonts.body) == ("Space Grotesk", "Plus Jakarta Sans")


def test_a_rendered_deck_gives_back_the_preferences_it_was_drawn_from(tmp_path: Path):
    style = StylePreferences(
        name="brand",
        slide_size=SlideSize(width_in=10, height_in=5.62),
        colors=Palette(main="#32AEB8", highlight="#F2A40D", text="#222222", background="#FAFAFA"),
        fonts=Fonts(heading="Georgia", body="Arial"),
        type_scale=TypeScale(title_pt=24, body_pt=12),
    )
    plan = SlidePlan(
        slide_id="s1", title="First slide", purpose="Introduce the topic",
        key_points=["Point one", "Point two"], source_pages=[1],
    )
    outline = DeckOutline(title="Fake deck", subtitle="A subtitle", slides=[plan])
    styled = [StyledSlide(plan=plan, layout_name=plan.visual_type, style_name=style.name)]
    artifact = PptxService().render(outline, styled, style, tmp_path / "brand.pptx")

    extracted = PreferencesExtractor().extract(Path(artifact.path))

    assert extracted.colors == style.colors
    assert extracted.fonts == style.fonts
    assert extracted.type_scale == style.type_scale
    assert extracted.slide_size == style.slide_size


def test_extracted_preferences_load_back_as_a_preferences_file(tmp_path: Path):
    style = PreferencesExtractor().extract(_deck(tmp_path))
    path = tmp_path / "preferences.json"
    path.write_text(style.model_dump_json(indent=2), encoding="utf-8")

    assert load_preferences(path) == style


def test_a_file_that_is_not_a_presentation_is_reported(tmp_path: Path):
    path = tmp_path / "broken.pptx"
    path.write_bytes(b"not a zip")

    with pytest.raises(ValueError, match="Could not read preferences from broken.pptx"):
        PreferencesExtractor().extract(path)
