from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class StylePreferences(StrictModel):
    name: str = Field(default="technical-minimal", min_length=1, max_length=100)
    tone: Literal["formal", "educational", "executive", "conversational"] = "educational"
    density: Literal["sparse", "balanced", "dense"] = "balanced"
    primary_color: str = "#1F4E79"
    accent_color: str = "#70AD47"
    font_family: str = "Aptos"
    include_speaker_notes: bool = True
    template_path: str | None = None


class DocumentChunk(StrictModel):
    id: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    text: str = Field(min_length=1)


class SourceDocument(StrictModel):
    filename: str
    pages: int = Field(ge=1)
    chunks: list[DocumentChunk]


class SlidePlan(StrictModel):
    slide_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=180)
    purpose: str = Field(min_length=1, max_length=500)
    key_points: list[str] = Field(min_length=1, max_length=8)
    source_chunk_ids: list[str] = Field(min_length=1)
    visual_type: Literal["title", "bullets", "comparison", "process", "concept", "summary"] = "bullets"
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
    document: SourceDocument | None = None
    outline: DeckOutline | None = None
    styled_slides: list[StyledSlide] = Field(default_factory=list)
    artifact: DeckArtifact | None = None
    events: list[ExecutionEvent] = Field(default_factory=list)
    error: str | None = None
    approved_outline: bool = False
    approved_deck: bool = False
