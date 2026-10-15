import base64
import io
from pathlib import Path

from PIL import Image

from pdf2deck.schemas import ImageBox, SourceDocument, SourceImage, SourcePage
from pdf2deck.services.llm_service import outline_messages


def _document(tmp_path: Path) -> SourceDocument:
    path = tmp_path / "img-p2-0.png"
    Image.new("RGBA", (1200, 600), (255, 0, 0, 128)).save(path)
    image = SourceImage(
        id="img-p2-0",
        page=2,
        path=str(path),
        width_px=1200,
        height_px=600,
        box=ImageBox(x=153, y=198, width=306, height=198),
        page_width_pt=612,
        page_height_pt=792,
    )
    pages = [SourcePage(number=1, text="Intro text."), SourcePage(number=2, text="Figure 2.1 Cells.")]
    return SourceDocument(filename="chapter.pdf", pages=pages, images=[image])


def test_images_are_listed_under_their_page(tmp_path: Path):
    _, human = outline_messages(_document(tmp_path), "educational", "balanced", 10)
    prompt = human.content[0]["text"]

    assert "[page 1]\nIntro text.\n\n[page 2]\nFigure 2.1 Cells.\nImages on this page:" in prompt
    assert (
        "- img-p2-0: 1200x600 px, drawn 306x198 pt, at x 25%-75%, y 25%-50% of the page"
        in prompt
    )


def test_each_image_is_attached_after_its_label_at_low_detail(tmp_path: Path):
    _, human = outline_messages(_document(tmp_path), "educational", "balanced", 10)
    label, block = human.content[1:]

    assert label == {"type": "text", "text": "[img-p2-0]"}
    assert block["image_url"]["detail"] == "low"
    url = block["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as preview:
        assert preview.size == (512, 256)
