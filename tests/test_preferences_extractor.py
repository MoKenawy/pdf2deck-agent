from pathlib import Path

import pytest
from pptx import Presentation
from pptx.dml.color import MSO_THEME_COLOR
from pptx.util import Inches, Pt

from pdf2deck.preferences import load_preferences
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

    assert (colors.main, colors.highlight) == (OFFICE_ACCENT_2, OFFICE_ACCENT_1)


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
