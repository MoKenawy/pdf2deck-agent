from pathlib import Path

from pypdf import PdfReader


class PdfService:
    def extract_pages(self, path: Path) -> list[str]:
        """Return the raw text of each page, in page order."""
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]

        if not any(text.strip() for text in pages):
            raise ValueError("No extractable text was found in the PDF.")

        return pages
