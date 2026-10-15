from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


HexColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
FontName = Annotated[str, Field(min_length=1, max_length=100)]
# PowerPoint accepts slide dimensions between 1 and 56 inches.
SlideInches = Annotated[float, Field(ge=1, le=56)]
FontPoints = Annotated[float, Field(ge=6, le=200)]


class SlideSize(StrictModel):
    width_in: SlideInches = 13.333
    height_in: SlideInches = 7.5


class Palette(StrictModel):
    main: HexColor = "#1F4E79"
    highlight: HexColor = "#70AD47"
    text: HexColor = "#000000"
    background: HexColor = "#FFFFFF"


class Fonts(StrictModel):
    heading: FontName = "Aptos"
    body: FontName = "Aptos"


class TypeScale(StrictModel):
    title_pt: FontPoints = 32
    body_pt: FontPoints = 18


class StylePreferences(StrictModel):
    name: str = Field(default="technical-minimal", min_length=1, max_length=100)
    tone: Literal["formal", "educational", "executive", "conversational"] = "educational"
    density: Literal["sparse", "balanced", "dense"] = "balanced"
    include_speaker_notes: bool = True
    slide_size: SlideSize = Field(default_factory=SlideSize)
    colors: Palette = Field(default_factory=Palette)
    fonts: Fonts = Field(default_factory=Fonts)
    type_scale: TypeScale = Field(default_factory=TypeScale)


class DocumentChunk(StrictModel):
    id: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    text: str = Field(min_length=1)


class PageRange(StrictModel):
    """The pages to build the deck from, numbered from 1; no last page means to the end."""

    first: int = Field(default=1, ge=1)
    last: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _first_not_after_last(self) -> PageRange:
        if self.last is not None and self.last < self.first:
            raise ValueError(f"First page {self.first} is after last page {self.last}.")
        return self

    def numbers(self, page_count: int) -> range:
        """The selected page numbers, checked against the PDF's page count."""
        last = page_count if self.last is None else self.last
        if self.first > page_count or last > page_count:
            raise ValueError(
                f"Pages {self.first}-{last} are outside the PDF, which has {page_count} pages."
            )
        return range(self.first, last + 1)


class SourcePage(StrictModel):
    number: int = Field(ge=1)
    text: str


class ImageBox(StrictModel):
    """Where an image is drawn on its page, in points from the page's top-left corner."""

    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class SourceImage(StrictModel):
    id: str = Field(min_length=1)
    page: int = Field(ge=1)
    path: str
    width_px: int = Field(ge=1)
    height_px: int = Field(ge=1)
    box: ImageBox
    page_width_pt: float = Field(gt=0)
    page_height_pt: float = Field(gt=0)


class SourceDocument(StrictModel):
    filename: str
    pages: list[SourcePage] = Field(min_length=1)
    images: list[SourceImage] = Field(default_factory=list)


class SlidePlan(StrictModel):
    slide_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=180)
    purpose: str = Field(min_length=1, max_length=500)
    key_points: list[str] = Field(min_length=1, max_length=8)
    source_pages: list[int] = Field(min_length=1)
    visual_type: Literal["title", "bullets", "comparison", "process", "concept", "summary"] = "bullets"
    image_id: str | None = None
    speaker_notes: str = ""


class DeckOutline(StrictModel):
    title: str = Field(min_length=1, max_length=180)
    subtitle: str = ""
    learning_objectives: list[str] = Field(default_factory=list, max_length=8)
    slides: list[SlidePlan] = Field(min_length=1)


class StyledSlide(StrictModel):
    plan: SlidePlan
    layout_name: str
    style_name: str
    image: SourceImage | None = None


class DeckArtifact(StrictModel):
    path: str
    slide_count: int = Field(ge=1)
    title: str


class ExecutionEvent(StrictModel):
    node: str
    status: Literal["started", "completed", "failed", "waiting"]
    message: str
    data: dict[str, str | int | float | bool] = Field(default_factory=dict)


class DeckState(StrictModel):
    run_id: str
    pdf_path: str
    style: StylePreferences
    page_range: PageRange = Field(default_factory=PageRange)
    document: SourceDocument | None = None
    outline: DeckOutline | None = None
    styled_slides: list[StyledSlide] = Field(default_factory=list)
    artifact: DeckArtifact | None = None
    events: list[ExecutionEvent] = Field(default_factory=list)
    error: str | None = None
    approved_outline: bool = False
    approved_deck: bool = False
