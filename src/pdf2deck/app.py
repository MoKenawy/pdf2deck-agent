from __future__ import annotations

import json
import uuid
from pathlib import Path

import gradio as gr
from langgraph.types import Command

from .config import get_settings
from .graph import DeckGraph
from .schemas import DeckState, StylePreferences


settings = get_settings()
graph = DeckGraph(settings).build()


def _initial_state(pdf_path: str, style: StylePreferences) -> DeckState:
    return DeckState(
        run_id=str(uuid.uuid4()),
        pdf_path=pdf_path,
        style=style,
    )


def run_deck(
    pdf_file: str | None,
    style_name: str,
    tone: str,
    density: str,
    font_family: str,
    template_file: str | None,
):
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
    config = {"configurable": {"thread_id": state.run_id}}

    events: list[str] = []
    for update in graph.stream(state.model_dump(), config=config, stream_mode="updates"):
        events.append(json.dumps(update, default=str, indent=2))
        yield "\n\n".join(events), None, state.run_id


def resume_outline(run_id: str, approved: bool):
    if not run_id:
        raise gr.Error("No active run.")
    config = {"configurable": {"thread_id": run_id}}
    result = graph.invoke(Command(resume={"approved": approved}), config=config)
    artifact = result.get("artifact")
    log = json.dumps(result, default=str, indent=2)
    yield log, artifact["path"] if artifact else None


def resume_deck(run_id: str, approved: bool):
    if not run_id:
        raise gr.Error("No active run.")
    config = {"configurable": {"thread_id": run_id}}
    result = graph.invoke(Command(resume={"approved": approved}), config=config)
    artifact = result.get("artifact")
    log = json.dumps(result, default=str, indent=2)
    yield log, artifact["path"] if artifact else None


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
            with gr.Column():
                log = gr.Textbox(label="Graph execution", lines=28)
                run_id = gr.Textbox(label="Run ID")
                output = gr.File(label="PPTX output")

        with gr.Row():
            approve_outline = gr.Button("Approve outline")
            reject_outline = gr.Button("Reject outline")
            approve_deck = gr.Button("Approve deck")
            reject_deck = gr.Button("Reject deck")

        run.click(
            run_deck,
            inputs=[pdf, style_name, tone, density, font, template],
            outputs=[log, output, run_id],
        )
        approve_outline.click(resume_outline, [run_id, gr.State(True)], [log, output])
        reject_outline.click(resume_outline, [run_id, gr.State(False)], [log, output])
        approve_deck.click(resume_deck, [run_id, gr.State(True)], [log, output])
        reject_deck.click(resume_deck, [run_id, gr.State(False)], [log, output])
    return demo


def main() -> None:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    build_ui().launch()


if __name__ == "__main__":
    main()
