from pdf2deck.services.chunking import chunk_pages


def test_pages_are_cleaned_and_split_at_the_size_limit():
    pages = ["  alpha  \n\n\n\nbeta\n\ngamma  ", "   ", "delta"]

    chunks = chunk_pages(pages, max_chunk_chars=11)

    assert [(c.id, c.text) for c in chunks] == [
        ("p1-c0", "alpha\n\nbeta"),
        ("p1-c1", "gamma"),
        ("p3-c0", "delta"),
    ]
