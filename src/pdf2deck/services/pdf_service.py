import hashlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from pypdf import PageObject, PdfReader
from pypdf.generic import StreamObject

from ..schemas import ImageBox, SourceDocument, SourceImage, SourcePage

logger = logging.getLogger(__name__)

# A PDF transformation matrix [a b c d e f]: x' = a*x + c*y + e, y' = b*x + d*y + f.
Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

# Images covering less of their page than this are decoration, whatever their resolution.
MIN_PAGE_COVERAGE = 0.01

# Modes PNG stores as they are; anything else (CMYK, 16-bit, palettes) is converted.
PNG_MODES = {"1", "L", "LA", "RGB", "RGBA"}


@dataclass(frozen=True)
class _Placement:
    """One image XObject drawn on one page, before it is decoded."""

    page: PageObject
    page_number: int
    name: str
    digest: str
    width_px: int
    height_px: int
    box: ImageBox
    page_width: float
    page_height: float


class PdfService:
    def extract_document(
        self,
        path: Path,
        image_dir: Path,
        *,
        min_image_px: int = 100,
        repeated_image_pages: int = 3,
        max_images: int = 40,
    ) -> SourceDocument:
        """Return each page's text and the content images, saved as PNGs in image_dir."""
        reader = PdfReader(str(path))
        texts = _page_texts(reader)
        images = self.extract_images(
            reader,
            image_dir,
            min_image_px=min_image_px,
            repeated_image_pages=repeated_image_pages,
            max_images=max_images,
        )
        return SourceDocument(
            filename=path.name,
            pages=[SourcePage(number=number, text=text) for number, text in enumerate(texts, start=1)],
            images=images,
        )

    def extract_pages(self, path: Path) -> list[str]:
        """Return the raw text of each page, in page order."""
        return _page_texts(PdfReader(str(path)))

    def extract_images(
        self,
        reader: PdfReader,
        image_dir: Path,
        *,
        min_image_px: int,
        repeated_image_pages: int,
        max_images: int,
    ) -> list[SourceImage]:
        """Save the images worth putting on a slide and say where each one is drawn.

        Logos, icons and other decoration are dropped: images too small in pixels or on
        the page, and images repeated on many pages. An image drawn on fewer pages than
        that is kept once, at its first page.

        Only images drawn directly by the page are found; ones inside form XObjects and
        inline images are skipped, and page rotation is ignored.
        """
        candidates = [
            placement
            for number, page in enumerate(reader.pages, start=1)
            for placement in _placements(page, number)
            if min(placement.width_px, placement.height_px) >= min_image_px
            and _coverage(placement) >= MIN_PAGE_COVERAGE
        ]

        pages_by_digest: dict[str, set[int]] = {}
        for placement in candidates:
            pages_by_digest.setdefault(placement.digest, set()).add(placement.page_number)

        images: list[SourceImage] = []
        seen: set[str] = set()
        per_page: dict[int, int] = {}
        for placement in candidates:
            if len(images) >= max_images:
                break
            if placement.digest in seen or len(pages_by_digest[placement.digest]) >= repeated_image_pages:
                continue
            seen.add(placement.digest)

            index = per_page.get(placement.page_number, 0)
            image_id = f"img-p{placement.page_number}-{index}"
            output = image_dir / f"{image_id}.png"
            try:
                size = _save_png(placement, output)
            except Exception as exc:  # noqa: BLE001
                # A filter pypdf or Pillow cannot decode should cost one image, not the run.
                logger.warning("Skipped %s on page %d: %s", placement.name, placement.page_number, exc)
                continue
            per_page[placement.page_number] = index + 1
            images.append(
                SourceImage(
                    id=image_id,
                    page=placement.page_number,
                    path=str(output),
                    width_px=size[0],
                    height_px=size[1],
                    box=placement.box,
                    page_width_pt=placement.page_width,
                    page_height_pt=placement.page_height,
                )
            )
        return images


def _page_texts(reader: PdfReader) -> list[str]:
    texts = [page.extract_text() or "" for page in reader.pages]
    if not any(text.strip() for text in texts):
        raise ValueError("No extractable text was found in the PDF.")
    return texts


def _placements(page: PageObject, page_number: int) -> Iterator[_Placement]:
    """Walk the page's drawing operators, tracking the transform, to place each image."""
    contents = page.get_contents()
    resources = page.get("/Resources")
    if contents is None or resources is None:
        return
    xobjects = resources.get_object().get("/XObject")
    if xobjects is None:
        return
    xobjects = xobjects.get_object()

    media = page.mediabox
    page_width, page_height = float(media.width), float(media.height)
    ctm = IDENTITY
    stack: list[Matrix] = []
    for operands, operator in contents.operations:
        if operator == b"q":
            stack.append(ctm)
        elif operator == b"Q":
            ctm = stack.pop() if stack else IDENTITY
        elif operator == b"cm":
            ctm = _multiply(tuple(float(value) for value in operands), ctm)  # type: ignore[arg-type]
        elif operator == b"Do":
            name = str(operands[0])
            ref = xobjects.get(name)
            xobject = ref.get_object() if ref is not None else None
            if not isinstance(xobject, StreamObject) or xobject.get("/Subtype") != "/Image":
                continue
            box = _page_box(ctm, float(media.left), float(media.top), page_width, page_height)
            if box is None:
                continue
            try:
                digest = hashlib.sha1(xobject.get_data()).hexdigest()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipped %s on page %d: %s", name, page_number, exc)
                continue
            yield _Placement(
                page=page,
                page_number=page_number,
                name=name,
                digest=digest,
                width_px=int(xobject.get("/Width", 0)),
                height_px=int(xobject.get("/Height", 0)),
                box=box,
                page_width=page_width,
                page_height=page_height,
            )


def _multiply(m: Matrix, n: Matrix) -> Matrix:
    """m then n, as PDF's `cm` operator composes a new matrix with the current one."""
    return (
        m[0] * n[0] + m[1] * n[2],
        m[0] * n[1] + m[1] * n[3],
        m[2] * n[0] + m[3] * n[2],
        m[2] * n[1] + m[3] * n[3],
        m[4] * n[0] + m[5] * n[2] + n[4],
        m[4] * n[1] + m[5] * n[3] + n[5],
    )


def _page_box(
    ctm: Matrix, left: float, top: float, page_width: float, page_height: float
) -> ImageBox | None:
    """The unit square an image is drawn into, mapped to the page and clipped to it."""
    a, b, c, d, e, f = ctm
    corners = [(a * x + c * y + e, b * x + d * y + f) for x, y in ((0, 0), (1, 0), (0, 1), (1, 1))]
    xs = [x - left for x, _ in corners]
    # PDF's y axis points up from the bottom; the box is measured down from the top.
    ys = [top - y for _, y in corners]
    x0, x1 = max(min(xs), 0.0), min(max(xs), page_width)
    y0, y1 = max(min(ys), 0.0), min(max(ys), page_height)
    if x1 <= x0 or y1 <= y0:
        return None
    return ImageBox(x=x0, y=y0, width=x1 - x0, height=y1 - y0)


def _coverage(placement: _Placement) -> float:
    box = placement.box
    return (box.width * box.height) / (placement.page_width * placement.page_height)


def _save_png(placement: _Placement, output: Path) -> tuple[int, int]:
    image = placement.page.images[placement.name].image
    if image is None:
        raise ValueError("pypdf could not decode the image")
    if image.mode == "P":
        image = image.convert("RGBA")
    elif image.mode not in PNG_MODES:
        image = image.convert("RGB")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG")
    return image.size
