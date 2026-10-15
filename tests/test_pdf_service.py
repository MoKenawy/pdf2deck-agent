from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import ContentStream, DictionaryObject, NameObject

from pdf2deck.schemas import PageRange
from pdf2deck.services.pdf_service import PdfService


def test_empty_pdf_is_rejected(tmp_path: Path):
    path = tmp_path / "empty.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as f:
        writer.write(f)

    with pytest.raises(ValueError, match="No extractable text"):
        PdfService().extract_document(path, tmp_path / "images")


def _image(width: int, height: int, color: str) -> Image.Image:
    return Image.new("RGB", (width, height), color)


def _image_pages(tmp_path: Path, *images: Image.Image) -> PdfReader:
    """One page per image, each image filling its page (Pillow draws them at 72 dpi)."""
    path = tmp_path / "images.pdf"
    first, *rest = images
    first.save(path, "PDF", resolution=72, save_all=True, append_images=rest)
    return PdfReader(str(path))


def _extract(reader: PdfReader, tmp_path: Path, **limits: int):
    options = {"min_image_px": 100, "repeated_image_pages": 3, "max_images": 40, **limits}
    return PdfService().extract_images(reader, tmp_path / "images", **options)


def test_image_is_saved_as_png_with_its_page_and_box(tmp_path: Path):
    image_page = _image_pages(tmp_path, _image(200, 100, "red")).pages[0]
    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    # Drawn 50 pt from the left and 250 pt up from the bottom, i.e. 50 pt down from the top.
    page.merge_transformed_page(image_page, Transformation().translate(50, 250))
    path = tmp_path / "placed.pdf"
    with path.open("wb") as f:
        writer.write(f)

    [image] = _extract(PdfReader(str(path)), tmp_path)

    assert image.id == "img-p1-0"
    assert image.page == 1
    assert (image.width_px, image.height_px) == (200, 100)
    assert (image.box.x, image.box.y, image.box.width, image.box.height) == pytest.approx(
        (50, 50, 200, 100)
    )
    assert (image.page_width_pt, image.page_height_pt) == (400, 400)
    with Image.open(image.path) as saved:
        assert saved.format == "PNG"
        assert saved.size == (200, 100)


def test_small_images_are_dropped(tmp_path: Path):
    reader = _image_pages(tmp_path, _image(50, 300, "red"), _image(300, 300, "blue"))

    assert [image.id for image in _extract(reader, tmp_path)] == ["img-p2-0"]


def test_images_repeated_on_many_pages_are_dropped(tmp_path: Path):
    logo = _image(150, 150, "green")
    reader = _image_pages(tmp_path, logo, _image(300, 200, "red"), logo, logo)

    assert [image.id for image in _extract(reader, tmp_path)] == ["img-p2-0"]


def test_an_image_on_a_few_pages_is_kept_once(tmp_path: Path):
    figure = _image(300, 200, "red")
    reader = _image_pages(tmp_path, figure, figure)

    assert [image.id for image in _extract(reader, tmp_path)] == ["img-p1-0"]


def test_max_images_keeps_the_earliest(tmp_path: Path):
    reader = _image_pages(
        tmp_path, _image(300, 200, "red"), _image(300, 200, "blue"), _image(300, 200, "green")
    )

    images = _extract(reader, tmp_path, max_images=2)

    assert [image.id for image in images] == ["img-p1-0", "img-p2-0"]


def _chapter(tmp_path: Path, page_count: int) -> Path:
    """Pages reading "Page n", each also showing a different 300x200 image."""
    colors = ["red", "green", "blue", "orange", "purple"]
    images = _image_pages(tmp_path, *(_image(300, 200, colors[n]) for n in range(page_count)))
    helvetica = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    writer = PdfWriter()
    for number in range(1, page_count + 1):
        page = writer.add_blank_page(width=400, height=400)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): helvetica}),
        })
        text = ContentStream(None, writer)
        text.set_data(f"BT /F1 12 Tf 20 380 Td (Page {number}) Tj ET".encode())
        page.replace_contents(text)
        page.merge_page(images.pages[number - 1])
    path = tmp_path / "chapter.pdf"
    with path.open("wb") as f:
        writer.write(f)
    return path


def test_page_range_keeps_only_those_pages_under_their_pdf_numbers(tmp_path: Path):
    path = _chapter(tmp_path, page_count=4)

    doc = PdfService().extract_document(
        path, tmp_path / "images", page_range=PageRange(first=2, last=3)
    )

    assert [(page.number, page.text.strip()) for page in doc.pages] == [(2, "Page 2"), (3, "Page 3")]
    assert [image.id for image in doc.images] == ["img-p2-0", "img-p3-0"]


def test_open_ended_page_range_runs_to_the_last_page(tmp_path: Path):
    path = _chapter(tmp_path, page_count=4)

    doc = PdfService().extract_document(path, tmp_path / "images", page_range=PageRange(first=3))

    assert [page.number for page in doc.pages] == [3, 4]


def test_page_range_outside_the_pdf_is_rejected(tmp_path: Path):
    path = _chapter(tmp_path, page_count=4)

    with pytest.raises(ValueError, match="Pages 3-9 are outside the PDF, which has 4 pages"):
        PdfService().extract_document(
            path, tmp_path / "images", page_range=PageRange(first=3, last=9)
        )
