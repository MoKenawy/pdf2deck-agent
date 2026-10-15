from ..schemas import DocumentChunk


def chunk_pages(pages: list[str], max_chunk_chars: int) -> list[DocumentChunk]:
    """Clean and chunk each page's text. Not used by the graph yet."""
    chunks: list[DocumentChunk] = []
    for page_number, text in enumerate(pages, start=1):
        paragraphs = clean_page_text(text)
        chunks.extend(chunk_paragraphs(paragraphs, page_number, max_chunk_chars))
    return chunks


def clean_page_text(text: str) -> list[str]:
    """Split raw page text into stripped, non-empty paragraphs."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def chunk_paragraphs(
    paragraphs: list[str], page_number: int, max_chunk_chars: int
) -> list[DocumentChunk]:
    """Greedily pack a page's paragraphs into chunks of at most max_chunk_chars."""
    chunks: list[DocumentChunk] = []
    buffer = ""

    def flush() -> None:
        chunks.append(
            DocumentChunk(
                id=f"p{page_number}-c{len(chunks)}",
                page_start=page_number,
                page_end=page_number,
                text=buffer,
            )
        )

    for paragraph in paragraphs:
        if len(buffer) + len(paragraph) + 2 <= max_chunk_chars:
            buffer = f"{buffer}\n\n{paragraph}".strip()
        else:
            if buffer:
                flush()
            buffer = paragraph

    if buffer:
        flush()

    return chunks
