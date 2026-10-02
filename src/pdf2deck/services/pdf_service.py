from pathlib import Path

from pypdf import PdfReader

from ..schemas import DocumentChunk, SourceDocument


class PdfService:
    def extract_and_chunk(self, path: Path, max_chunk_chars: int) -> SourceDocument:
        reader = PdfReader(str(path))
        chunks: list[DocumentChunk] = []

        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue

            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            buffer = ""
            chunk_index = 0

            for paragraph in paragraphs:
                if len(buffer) + len(paragraph) + 2 <= max_chunk_chars:
                    buffer = f"{buffer}\n\n{paragraph}".strip()
                else:
                    if buffer:
                        chunks.append(
                            DocumentChunk(
                                id=f"p{page_number}-c{chunk_index}",
                                page_start=page_number,
                                page_end=page_number,
                                text=buffer,
                            )
                        )
                        chunk_index += 1
                    buffer = paragraph

            if buffer:
                chunks.append(
                    DocumentChunk(
                        id=f"p{page_number}-c{chunk_index}",
                        page_start=page_number,
                        page_end=page_number,
                        text=buffer,
                    )
                )

        if not chunks:
            raise ValueError("No extractable text was found in the PDF.")

        return SourceDocument(
            filename=path.name,
            pages=len(reader.pages),
            chunks=chunks,
        )
