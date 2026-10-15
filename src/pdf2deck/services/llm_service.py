import base64
import io
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from PIL import Image

from ..config import Settings
from ..prompts import OUTLINE_SYSTEM, OUTLINE_USER, REVISION_SYSTEM
from ..schemas import DeckOutline, SourceDocument, SourceImage

# OpenAI's low detail level reads images at 512 px, so larger ones only cost upload time.
IMAGE_PREVIEW_PX = 512


class LlmService:
    def __init__(self, settings: Settings) -> None:
        self.model = ChatOpenAI(
            model=settings.model_name,
            temperature=settings.model_temperature,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    def create_outline(
        self,
        document: SourceDocument,
        tone: str,
        density: str,
        max_slides: int,
    ) -> DeckOutline:
        structured = self.model.with_structured_output(DeckOutline)
        return structured.invoke(outline_messages(document, tone, density, max_slides))

    def revise_outline(self, outline: DeckOutline, document: SourceDocument) -> DeckOutline:
        prompt = (
            f"CURRENT OUTLINE:\n{outline.model_dump_json(indent=2)}\n\n"
            f"SOURCE:\n{source_text(document)}"
        )
        structured = self.model.with_structured_output(DeckOutline)
        return structured.invoke([
            SystemMessage(REVISION_SYSTEM),
            HumanMessage([{"type": "text", "text": prompt}, *image_blocks(document)]),
        ])


def outline_messages(
    document: SourceDocument, tone: str, density: str, max_slides: int
) -> list[BaseMessage]:
    """The outline request: page text with each page's image list, then the images."""
    prompt = OUTLINE_USER.format(
        tone=tone,
        density=density,
        max_slides=max_slides,
        source=source_text(document),
    )
    return [
        SystemMessage(OUTLINE_SYSTEM),
        HumanMessage([{"type": "text", "text": prompt}, *image_blocks(document)]),
    ]


def source_text(document: SourceDocument) -> str:
    images_by_page: dict[int, list[SourceImage]] = {}
    for image in document.images:
        images_by_page.setdefault(image.page, []).append(image)

    blocks = []
    for page in document.pages:
        block = f"[page {page.number}]\n{page.text.strip()}"
        if page.number in images_by_page:
            listed = "\n".join(f"- {_describe(image)}" for image in images_by_page[page.number])
            block += f"\nImages on this page:\n{listed}"
        blocks.append(block)
    return "\n\n".join(blocks)


def image_blocks(document: SourceDocument) -> list[dict[str, Any]]:
    """A label and a low-detail image block for each image, in document order."""
    blocks: list[dict[str, Any]] = []
    for image in document.images:
        blocks.append({"type": "text", "text": f"[{image.id}]"})
        blocks.append({
            "type": "image_url",
            "image_url": {"url": _data_url(Path(image.path)), "detail": "low"},
        })
    return blocks


def _describe(image: SourceImage) -> str:
    box = image.box
    left, right = box.x / image.page_width_pt, (box.x + box.width) / image.page_width_pt
    top, bottom = box.y / image.page_height_pt, (box.y + box.height) / image.page_height_pt
    return (
        f"{image.id}: {image.width_px}x{image.height_px} px, "
        f"drawn {box.width:.0f}x{box.height:.0f} pt, "
        f"at x {left:.0%}-{right:.0%}, y {top:.0%}-{bottom:.0%} of the page"
    )


def _data_url(path: Path) -> str:
    with Image.open(path) as source:
        image = source.convert("RGBA")
    image.thumbnail((IMAGE_PREVIEW_PX, IMAGE_PREVIEW_PX))
    # JPEG has no alpha channel, so transparent areas are flattened onto white.
    flat = Image.new("RGB", image.size, "white")
    flat.paste(image, mask=image.getchannel("A"))
    buffer = io.BytesIO()
    flat.save(buffer, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
