from __future__ import annotations

from pathlib import Path
from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .config import Settings
from .schemas import DeckState, ExecutionEvent, StyledSlide
from .services.llm_service import LlmService
from .services.pdf_service import PdfService
from .services.pptx_service import PptxService


class DeckGraph:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.pdf = PdfService()
        self.llm = LlmService(settings)
        self.pptx = PptxService()

    @staticmethod
    def _event(
        state: DeckState, node: str, status: Literal["started", "completed", "failed", "waiting"],
        message: str,
    ) -> list[ExecutionEvent]:
        return [*state.events, ExecutionEvent(node=node, status=status, message=message)]

    def validate_input(self, state: DeckState) -> dict:
        path = Path(state.pdf_path)
        if not path.exists() or path.suffix.lower() != ".pdf":
            raise ValueError("Input must be an existing .pdf file.")
        if path.stat().st_size > self.settings.max_pdf_mb * 1024 * 1024:
            raise ValueError("PDF exceeds configured size limit.")
        return {"events": self._event(state, "validate_input", "completed", "Input validated.")}

    def extract_pdf(self, state: DeckState) -> dict:
        doc = self.pdf.extract_and_chunk(
            Path(state.pdf_path), self.settings.max_chunk_chars
        )
        return {
            "document": doc,
            "events": self._event(
                state, "extract_pdf", "completed",
                f"Extracted {doc.pages} pages into {len(doc.chunks)} chunks.",
            ),
        }

    def build_outline(self, state: DeckState) -> dict:
        if state.document is None:
            raise ValueError("Document is required before outline generation.")
        outline = self.llm.create_outline(
            state.document,
            state.style.tone,
            state.style.density,
            self.settings.max_slides,
        )
        return {
            "outline": outline,
            "events": self._event(state, "build_outline", "completed", "Outline generated."),
        }

    def approve_outline(self, state: DeckState) -> dict:
        decision = interrupt({
            "checkpoint": "outline_review",
            "message": "Review the generated outline. Resume with {'approved': true} or {'approved': false}.",
            "outline": state.outline.model_dump() if state.outline else None,
        })
        approved = bool(decision.get("approved", False))
        if not approved:
            raise ValueError("Outline was rejected. Restart the run after revising style/input.")
        return {
            "approved_outline": True,
            "events": self._event(state, "approve_outline", "completed", "Outline approved."),
        }

    def map_style(self, state: DeckState) -> dict:
        if state.outline is None:
            raise ValueError("Outline is required.")
        styled = [
            StyledSlide(
                plan=slide,
                layout_name=slide.visual_type,
                style_name=state.style.name,
            )
            for slide in state.outline.slides
        ]
        return {
            "styled_slides": styled,
            "events": self._event(state, "map_style", "completed", "Style mapped to slide plans."),
        }

    def render_pptx(self, state: DeckState) -> dict:
        if state.outline is None:
            raise ValueError("Outline is required.")
        output = self.settings.output_dir / f"{state.run_id}.pptx"
        artifact = self.pptx.render(
            state.outline,
            state.styled_slides,
            state.style,
            output,
        )
        return {
            "artifact": artifact,
            "events": self._event(state, "render_pptx", "completed", f"Created {artifact.path}."),
        }

    def validate_artifact(self, state: DeckState) -> dict:
        if state.artifact is None:
            raise ValueError("Artifact is missing.")
        path = Path(state.artifact.path)
        if not path.exists() or path.stat().st_size == 0:
            raise ValueError("Rendered artifact is missing or empty.")
        return {
            "events": self._event(state, "validate_artifact", "completed", "PPTX artifact validated.")
        }

    def approve_deck(self, state: DeckState) -> dict:
        decision = interrupt({
            "checkpoint": "deck_review",
            "message": "Review the generated deck. Resume with {'approved': true}.",
            "artifact": state.artifact.model_dump() if state.artifact else None,
        })
        approved = bool(decision.get("approved", False))
        if not approved:
            raise ValueError("Deck was rejected.")
        return {
            "approved_deck": True,
            "events": self._event(state, "approve_deck", "completed", "Deck approved."),
        }

    def build(self):
        graph = StateGraph(DeckState)
        graph.add_node("validate_input", self.validate_input)
        graph.add_node("extract_pdf", self.extract_pdf)
        graph.add_node("build_outline", self.build_outline)
        graph.add_node("approve_outline", self.approve_outline)
        graph.add_node("map_style", self.map_style)
        graph.add_node("render_pptx", self.render_pptx)
        graph.add_node("validate_artifact", self.validate_artifact)
        graph.add_node("approve_deck", self.approve_deck)

        graph.add_edge(START, "validate_input")
        graph.add_edge("validate_input", "extract_pdf")
        graph.add_edge("extract_pdf", "build_outline")
        graph.add_edge("build_outline", "approve_outline")
        graph.add_edge("approve_outline", "map_style")
        graph.add_edge("map_style", "render_pptx")
        graph.add_edge("render_pptx", "validate_artifact")
        graph.add_edge("validate_artifact", "approve_deck")
        graph.add_edge("approve_deck", END)

        checkpointer = InMemorySaver()
        return graph.compile(checkpointer=checkpointer)
