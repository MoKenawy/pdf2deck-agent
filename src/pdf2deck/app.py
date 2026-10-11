from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Iterator
from typing import Any

import gradio as gr
from langgraph.types import Command

from .config import get_settings
from .graph import DECK_REVIEW, OUTLINE_REVIEW, DeckGraph
from .schemas import DeckOutline, DeckState, StylePreferences


logger = logging.getLogger(__name__)

settings = get_settings()
graph = DeckGraph(settings).build()

OUTLINE_PLACEHOLDER = "_The outline will appear here once it has been generated._"

# Shown while a node is running; nodes not listed here finish near-instantly.
STEP_STATUS = {
    "extract_pdf": "Extracting text from the PDF…",
    "build_outline": (
        f"Generating the outline with `{settings.model_name}`… "
        "this is the slow step and can take several minutes for a long chapter."
    ),
    "render_pptx": "Rendering the PowerPoint…",
}

# One UI update: status, outline, log, PPTX path, then the four review buttons.
View = tuple[Any, ...]


def _initial_state(pdf_path: str, style: StylePreferences) -> DeckState:
    return DeckState(
        run_id=str(uuid.uuid4()),
        pdf_path=pdf_path,
        style=style,
    )


def _config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def _pending_checkpoint(run_id: str) -> str | None:
    interrupts = graph.get_state(_config(run_id)).interrupts
    return interrupts[0].value["checkpoint"] if interrupts else None


def _outline_markdown(outline: DeckOutline | None) -> str:
    if outline is None:
        return OUTLINE_PLACEHOLDER
    blocks = [f"## {outline.title}"]
    if outline.subtitle:
        blocks.append(f"*{outline.subtitle}*")
    if outline.learning_objectives:
        blocks.append("**Learning objectives**")
        blocks.append("\n".join(f"- {item}" for item in outline.learning_objectives))
    for number, slide in enumerate(outline.slides, start=1):
        blocks.append(f"### {number}. {slide.title} · `{slide.visual_type}`")
        blocks.append(f"*{slide.purpose}*")
        blocks.append("\n".join(f"- {point}" for point in slide.key_points))
    return "\n\n".join(blocks)


def _status(values: dict[str, Any], pending: str | None) -> str:
    if pending == OUTLINE_REVIEW:
        return "**Outline ready for review.** Approve it to render the deck."
    if pending == DECK_REVIEW:
        return (
            f"**Deck rendered ({values['artifact'].slide_count} slides).** "
            "Download it below, then approve or reject it."
        )
    if values.get("approved_deck"):
        return "**Deck approved.** The final PPTX is available below."
    return "Running…"


def _view(
    status: str, values: dict[str, Any], pending: str | None, running: str | None = None
) -> View:
    # State values are the pydantic models from schemas.py, not plain dicts.
    artifact = values.get("artifact")
    log = [f"[{event.status}] {event.node}: {event.message}" for event in values.get("events", [])]
    if running:
        log.append(f"[started] {running}: running…")
    if pending:
        log.append(f"[waiting] {pending}: waiting for your review.")
    return (
        status,
        _outline_markdown(values.get("outline")),
        "\n".join(log),
        artifact.path if artifact else None,
        gr.Button(interactive=pending == OUTLINE_REVIEW),
        gr.Button(interactive=pending == OUTLINE_REVIEW),
        gr.Button(interactive=pending == DECK_REVIEW),
        gr.Button(interactive=pending == DECK_REVIEW),
    )


def _drive(graph_input: Any, run_id: str) -> Iterator[View]:
    """Run the graph until it finishes or pauses for review, yielding UI updates."""
    config = _config(run_id)
    values = dict(graph.get_state(config).values)
    started: dict[str, float] = {}
    yield _view("Running…", values, None)
    try:
        for mode, payload in graph.stream(
            graph_input, config=config, stream_mode=["tasks", "updates"]
        ):
            if mode == "updates":
                for node_update in payload.values():
                    if isinstance(node_update, dict):
                        values.update(node_update)
            elif "input" in payload:
                # Task start: surface it now, since updates only arrive when a node finishes.
                node = payload["name"]
                started[payload["id"]] = time.perf_counter()
                logger.info("run %s: %s started", run_id, node)
                yield _view(STEP_STATUS.get(node, "Running…"), values, None, running=node)
            elif payload["id"] in started:
                elapsed = time.perf_counter() - started[payload["id"]]
                logger.info("run %s: %s finished in %.1fs", run_id, payload["name"], elapsed)
    except ValueError as exc:
        # Nodes raise ValueError for invalid input and for rejected reviews.
        logger.warning("run %s: stopped: %s", run_id, exc)
        yield _view(f"**Stopped:** {exc}", values, None)
        return
    except Exception as exc:
        # Anything else (model API errors, rendering bugs) must not leave the UI on "Running…".
        logger.exception("run %s: failed", run_id)
        yield _view(f"**Failed:** {type(exc).__name__}: {exc}", values, None)
        return
    pending = _pending_checkpoint(run_id)
    if pending:
        logger.info("run %s: waiting for %s", run_id, pending)
    yield _view(_status(values, pending), values, pending)


def run_deck(
    pdf_file: str | None,
    style_name: str,
    tone: str,
    density: str,
    font_family: str,
    template_file: str | None,
) -> Iterator[View]:
    if not pdf_file:
        raise gr.Error("Upload a PDF first.")

    style = StylePreferences(
        name=style_name,
        tone=tone,
        density=density,
        font_family=font_family,
        template_path=template_file,
    )
    state = _initial_state(pdf_file, style)
    for view in _drive(state.model_dump(), state.run_id):
        yield (state.run_id, *view)


def _resume(run_id: str, approved: bool, checkpoint: str, subject: str) -> Iterator[View]:
    if not run_id:
        raise gr.Error("No active run.")
    # Both reviews resume the same thread, so make sure this is the one that is pending.
    if _pending_checkpoint(run_id) != checkpoint:
        raise gr.Error(f"No {subject} is waiting for review.")
    yield from _drive(Command(resume={"approved": approved}), run_id)


def resume_outline(run_id: str, approved: bool) -> Iterator[View]:
    yield from _resume(run_id, approved, OUTLINE_REVIEW, "outline")


def resume_deck(run_id: str, approved: bool) -> Iterator[View]:
    yield from _resume(run_id, approved, DECK_REVIEW, "deck")


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="PDF2Deck Agent") as demo:
        gr.Markdown("# PDF → Styled PowerPoint Agent")
        with gr.Row():
            with gr.Column():
                pdf = gr.File(file_types=[".pdf"], type="filepath", label="Chapter PDF")
                template = gr.File(file_types=[".pptx"], type="filepath", label="Optional PPTX template")
                style_name = gr.Textbox(value="technical-minimal", label="Style name")
                tone = gr.Dropdown(["formal", "educational", "executive", "conversational"], value="educational", label="Tone")
                density = gr.Dropdown(["sparse", "balanced", "dense"], value="balanced", label="Density")
                font = gr.Textbox(value="Aptos", label="Font")
                run = gr.Button("Generate", variant="primary")
                log = gr.Textbox(label="Graph execution", lines=10)
                run_id = gr.Textbox(label="Run ID")
            with gr.Column():
                status = gr.Markdown("Upload a PDF and press **Generate**.")
                outline = gr.Markdown(OUTLINE_PLACEHOLDER, container=True, max_height=520)
                with gr.Row():
                    approve_outline = gr.Button("Approve outline", interactive=False)
                    reject_outline = gr.Button("Reject outline", interactive=False)
                output = gr.File(label="PPTX output")
                with gr.Row():
                    approve_deck = gr.Button("Approve deck", interactive=False)
                    reject_deck = gr.Button("Reject deck", interactive=False)

        view = [
            status, outline, log, output,
            approve_outline, reject_outline, approve_deck, reject_deck,
        ]
        run.click(
            run_deck,
            inputs=[pdf, style_name, tone, density, font, template],
            outputs=[run_id, *view],
        )
        approve_outline.click(resume_outline, [run_id, gr.State(True)], view)
        reject_outline.click(resume_outline, [run_id, gr.State(False)], view)
        approve_deck.click(resume_deck, [run_id, gr.State(True)], view)
        reject_deck.click(resume_deck, [run_id, gr.State(False)], view)
    return demo


def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("pdf2deck").setLevel(logging.INFO)
    # The OpenAI client reports request retries at INFO, which explains slow outline calls.
    logging.getLogger("openai").setLevel(logging.INFO)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    build_ui().launch()


if __name__ == "__main__":
    main()
