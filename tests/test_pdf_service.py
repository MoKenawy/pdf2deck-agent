from pathlib import Path

from pypdf import PdfWriter

from pdf2deck.services.pdf_service import PdfService


def test_empty_pdf_is_rejected(tmp_path: Path):
    path = tmp_path / "empty.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as f:
        writer.write(f)

    try:
        PdfService().extract_pages(path)
    except ValueError as exc:
        assert "No extractable text" in str(exc)
    else:
        raise AssertionError("Expected extraction failure")
