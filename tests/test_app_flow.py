from pathlib import Path

import gradio as gr
import pytest

from pdf2deck.config import Settings
from pdf2deck.graph import DeckGraph
from pdf2deck.schemas import DeckOutline, DocumentChunk, SlidePlan, SourceDocument


class FakePdf:
    def extract_and_chunk(self, path: Path, max_chunk_chars: int) -> SourceDocument:
        chunk = DocumentChunk(id="p1-c0", page_start=1, page_end=1, text="Source text.")
        return SourceDocument(filename=path.name, pages=1, chunks=[chunk])


class FakeLlm:
    def create_outline(self, document, tone, density, max_slides) -> DeckOutline:
        slide = SlidePlan(
            slide_id="s1",
            title="First slide",
            purpose="Introduce the topic",
            key_points=["Point one", "Point two"],
            source_chunk_ids=["p1-c0"],
        )
        return DeckOutline(title="Fake deck", learning_objectives=["Learn it"], slides=[slide])


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    import pdf2deck.app as app_module

    deck = DeckGraph(Settings(output_dir=tmp_path / "outputs"))
    deck.pdf = FakePdf()
    deck.llm = FakeLlm()
    monkeypatch.setattr(app_module, "graph", deck.build())
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
    assert "build_outline: Outline generated." in log
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


def test_rejecting_outline_stops_the_run(app, pdf_path):
    run_id = _generate(app, pdf_path)[0]

    status, _, _, output, *buttons = list(app.resume_outline(run_id, False))[-1]
    assert "Outline was rejected" in status
    assert output is None
    assert _enabled(buttons) == [False, False, False, False]
