from pathlib import Path

import gradio as gr
import pytest
from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches

from pdf2deck.config import Settings
from pdf2deck.graph import DeckGraph
from pdf2deck.preferences import load_preferences
from pdf2deck.schemas import (
    DeckOutline,
    ImageBox,
    PageRange,
    SlidePlan,
    SourceDocument,
    SourceImage,
    SourcePage,
)


class FakePdf:
    """A PDF with `page_count` pages; by default one, so runs see "1 pages"."""

    def __init__(self) -> None:
        self.images: list[SourceImage] = []
        self.page_count = 1

    def extract_document(
        self, path: Path, image_dir: Path, page_range: PageRange | None = None, **limits
    ) -> SourceDocument:
        numbers = (page_range or PageRange()).numbers(self.page_count)
        return SourceDocument(
            filename=path.name,
            pages=[SourcePage(number=number, text="Source text.") for number in numbers],
            images=self.images,
        )


class FakeLlm:
    def __init__(self) -> None:
        self.image_ids: list[str | None] = [None]

    def create_outline(self, document, tone, density, max_slides) -> DeckOutline:
        slides = [
            SlidePlan(
                slide_id=f"s{number}",
                title="First slide" if number == 1 else f"Slide {number}",
                purpose="Introduce the topic",
                key_points=["Point one", "Point two"],
                source_pages=[1],
                image_id=image_id,
            )
            for number, image_id in enumerate(self.image_ids, start=1)
        ]
        return DeckOutline(title="Fake deck", learning_objectives=["Learn it"], slides=slides)


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    import pdf2deck.app as app_module

    # Isolated from the developer's .env: outputs go to tmp_path and no default file applies.
    settings = Settings(output_dir=tmp_path / "outputs", default_preferences_path=None)
    deck = DeckGraph(settings)
    deck.pdf = FakePdf()
    deck.llm = FakeLlm()
    monkeypatch.setattr(app_module, "graph", deck.build())
    monkeypatch.setattr(app_module, "settings", settings)
    # Lets a test choose what the fakes return.
    monkeypatch.setattr(app_module, "deck", deck, raising=False)
    return app_module


@pytest.fixture
def pdf_path(tmp_path: Path) -> str:
    path = tmp_path / "chapter.pdf"
    path.write_bytes(b"%PDF-1.4")
    return str(path)


def _generate(app, pdf_path: str):
    views = list(app.run_deck(pdf_path, "technical-minimal", "educational", "balanced", "Aptos", None))
    return views[-1]


def _enabled(buttons) -> list[bool]:
    return [button.interactive for button in buttons]


def test_generate_shows_outline_and_waits_for_outline_review(app, pdf_path):
    run_id, status, outline, log, output, *buttons = _generate(app, pdf_path)

    assert run_id
    assert "Outline ready" in status
    assert "## Fake deck" in outline
    assert "### 1. First slide" in outline
    assert "- Point one" in outline
    assert "build_outline: Outline generated (0 images placed)." in log
    assert output is None
    assert _enabled(buttons) == [True, True, False, False]


def test_generate_reports_the_running_step_before_it_finishes(app, pdf_path):
    views = list(app.run_deck(pdf_path, "technical-minimal", "educational", "balanced", "Aptos", None))

    during_outline = next(view for view in views if "[started] build_outline" in view[3])
    assert "Generating the outline" in during_outline[1]
    assert "extract_pdf: Extracted 1 pages" in during_outline[3]
    assert "Outline generated" not in during_outline[3]
    assert "[waiting] outline_review" in views[-1][3]


def test_model_failure_is_reported_instead_of_leaving_the_run_spinning(app, pdf_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(FakeLlm, "create_outline", fail)

    _, status, _, log, output, *buttons = _generate(app, pdf_path)
    assert status == "**Failed:** RuntimeError: model unavailable"
    assert "extract_pdf: Extracted 1 pages" in log
    assert output is None
    assert _enabled(buttons) == [False, False, False, False]


def test_approving_outline_then_deck_returns_the_pptx(app, pdf_path):
    run_id = _generate(app, pdf_path)[0]

    status, outline, _, output, *buttons = list(app.resume_outline(run_id, True))[-1]
    assert "Deck rendered (2 slides)" in status
    assert "## Fake deck" in outline
    assert Path(output).exists()
    assert _enabled(buttons) == [False, False, True, True]

    status, _, log, output, *buttons = list(app.resume_deck(run_id, True))[-1]
    assert "Deck approved" in status
    assert "approve_deck: Deck approved." in log
    assert Path(output).exists()
    assert _enabled(buttons) == [False, False, False, False]


def test_deck_review_cannot_resume_a_pending_outline_review(app, pdf_path):
    run_id = _generate(app, pdf_path)[0]

    with pytest.raises(gr.Error, match="No deck is waiting"):
        list(app.resume_deck(run_id, True))


def _render_with(app, pdf_path: str, preferences_file: str | None) -> Presentation:
    views = list(
        app.run_deck(pdf_path, "technical-minimal", "educational", "balanced", "Aptos", preferences_file)
    )
    output = list(app.resume_outline(views[-1][0], True))[-1][3]
    return Presentation(output)


def _fonts(prs: Presentation) -> set[str]:
    return {
        run.font.name
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_text_frame
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
    }


def test_form_sets_the_style_when_no_preferences_file_is_given(app, pdf_path):
    assert _fonts(_render_with(app, pdf_path, None)) == {"Aptos"}


def test_uploaded_preferences_file_wins_over_the_form(app, pdf_path, tmp_path):
    preferences = tmp_path / "preferences.json"
    preferences.write_text(
        '{"fonts": {"heading": "Georgia", "body": "Arial"}, "slide_size": {"width_in": 10, "height_in": 5.62}}',
        encoding="utf-8",
    )

    prs = _render_with(app, pdf_path, str(preferences))

    assert _fonts(prs) == {"Georgia", "Arial"}
    assert prs.slide_width == Inches(10)


def test_configured_default_preferences_file_is_used_when_none_is_uploaded(
    app, pdf_path, tmp_path, monkeypatch
):
    default = tmp_path / "default.json"
    default.write_text('{"fonts": {"heading": "Verdana", "body": "Verdana"}}', encoding="utf-8")
    monkeypatch.setattr(app.settings, "default_preferences_path", default)

    assert _fonts(_render_with(app, pdf_path, None)) == {"Verdana"}
    assert all(not field["interactive"] for field in app.form_fields(None))


def test_invalid_preferences_file_stops_before_the_run_starts(app, pdf_path, tmp_path):
    preferences = tmp_path / "preferences.json"
    preferences.write_text('{"colors": {"main": "teal"}}', encoding="utf-8")

    with pytest.raises(gr.Error, match="colors.main"):
        list(app.run_deck(pdf_path, "technical-minimal", "educational", "balanced", "Aptos", str(preferences)))


def test_form_fields_lock_while_a_preferences_file_is_present(app):
    assert all(not field["interactive"] for field in app.form_fields("preferences.json"))
    assert all(field["interactive"] for field in app.form_fields(None))


def test_extract_button_writes_a_preferences_file_that_loads(app, tmp_path):
    template = tmp_path / "Brand Deck.pptx"
    Presentation().save(template)

    content, path = app.extract_preferences(str(template))

    assert Path(path).name == "brand-deck.preferences.json"
    assert Path(path).read_text(encoding="utf-8") == content
    assert load_preferences(Path(path)).name == "brand-deck"


def test_extract_button_reports_a_file_that_is_not_a_presentation(app, tmp_path):
    template = tmp_path / "broken.pptx"
    template.write_bytes(b"not a zip")

    with pytest.raises(gr.Error, match="Could not read preferences from broken.pptx"):
        app.extract_preferences(str(template))


def test_rejecting_outline_stops_the_run(app, pdf_path):
    run_id = _generate(app, pdf_path)[0]

    status, _, _, output, *buttons = list(app.resume_outline(run_id, False))[-1]
    assert "Outline was rejected" in status
    assert output is None
    assert _enabled(buttons) == [False, False, False, False]


def _figure(tmp_path: Path) -> SourceImage:
    path = tmp_path / "img-p1-0.png"
    Image.new("RGB", (400, 300), "red").save(path)
    return SourceImage(
        id="img-p1-0",
        page=1,
        path=str(path),
        width_px=400,
        height_px=300,
        box=ImageBox(x=100, y=100, width=200, height=150),
        page_width_pt=612,
        page_height_pt=792,
    )


def test_chosen_image_is_shown_in_the_outline_and_placed_on_its_slide(app, pdf_path, tmp_path):
    app.deck.pdf.images = [_figure(tmp_path)]
    app.deck.llm.image_ids = ["img-p1-0"]

    _, _, outline, log, *_ = _generate(app, pdf_path)
    assert "🖼 Image `img-p1-0`" in outline
    assert "extract_pdf: Extracted 1 pages and 1 images." in log
    assert "Outline generated (1 images placed)." in log

    prs = _render_with(app, pdf_path, None)
    pictures = [s for s in prs.slides[1].shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(pictures) == 1


def test_invented_and_reused_image_ids_are_cleared(app, pdf_path, tmp_path):
    app.deck.pdf.images = [_figure(tmp_path)]
    app.deck.llm.image_ids = ["img-p9-9", "img-p1-0", "img-p1-0"]

    _, _, outline, log, *_ = _generate(app, pdf_path)

    assert "img-p9-9" not in outline
    assert outline.count("🖼 Image `img-p1-0`") == 1
    assert "Outline generated (1 images placed)." in log


def test_page_range_from_the_form_selects_the_pages(app, pdf_path):
    app.deck.pdf.page_count = 10

    views = list(app.run_deck(
        pdf_path, "technical-minimal", "educational", "balanced", "Aptos", None, "3", " 5 "
    ))

    assert "extract_pdf: Extracted 3 pages (3-5) and 0 images." in views[-1][3]
    assert "Outline ready" in views[-1][1]


def test_page_range_past_the_end_of_the_pdf_stops_the_run(app, pdf_path):
    app.deck.pdf.page_count = 10

    views = list(app.run_deck(
        pdf_path, "technical-minimal", "educational", "balanced", "Aptos", None, "8", "12"
    ))

    assert views[-1][1] == "**Stopped:** Pages 8-12 are outside the PDF, which has 10 pages."


def test_reversed_page_range_is_refused_before_the_run_starts(app, pdf_path):
    with pytest.raises(gr.Error, match="Invalid page range: First page 5 is after last page 3"):
        list(app.run_deck(
            pdf_path, "technical-minimal", "educational", "balanced", "Aptos", None, "5", "3"
        ))


@pytest.mark.parametrize("first, last", [("abc", ""), ("2.5", ""), ("", "-4")])
def test_page_range_that_is_not_a_page_number_is_refused(app, pdf_path, first, last):
    with pytest.raises(gr.Error, match="is not a page number"):
        list(app.run_deck(
            pdf_path, "technical-minimal", "educational", "balanced", "Aptos", None, first, last
        ))


def test_empty_page_range_fields_use_the_whole_pdf(app, pdf_path):
    app.deck.pdf.page_count = 4

    views = list(app.run_deck(
        pdf_path, "technical-minimal", "educational", "balanced", "Aptos", None, "", "  "
    ))

    assert "extract_pdf: Extracted 4 pages and 0 images." in views[-1][3]
