from pathlib import Path

import pytest
from pypdf import PdfWriter

from pdf2deck.services.pdf_service import PdfService


def test_empty_pdf_is_rejected(tmp_path: Path):
    path = tmp_path / "empty.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as f:
        writer.write(f)

    with pytest.raises(ValueError, match="No extractable text"):
        PdfService().extract_document(path)
