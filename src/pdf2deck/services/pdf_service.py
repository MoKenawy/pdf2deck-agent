from pathlib import Path

from pypdf import PdfReader

from ..schemas import SourceDocument, SourcePage


class PdfService:
    def extract_document(self, path: Path) -> SourceDocument:
        """Return the text of each page."""
        reader = PdfReader(str(path))
        texts = _page_texts(reader)
        return SourceDocument(
            filename=path.name,
            pages=[SourcePage(number=number, text=text) for number, text in enumerate(texts, start=1)],
        )

    def extract_pages(self, path: Path) -> list[str]:
        """Return the raw text of each page, in page order."""
        return _page_texts(PdfReader(str(path)))


def _page_texts(reader: PdfReader) -> list[str]:
    texts = [page.extract_text() or "" for page in reader.pages]
    if not any(text.strip() for text in texts):
        raise ValueError("No extractable text was found in the PDF.")
    return texts
