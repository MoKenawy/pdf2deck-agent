# PDF2Deck Agent

A production-oriented MVP that converts a PDF chapter into a structured, styled PowerPoint deck.

## Demo

[![PDF2Deck Agent turning a biology chapter into a deck](docs/ui-guide/img/overview.jpg)](https://drive.google.com/file/d/1uawnigtD5zGxpa5VG-PiQdWk6DqU9cnA/view)

▶ **[Watch the test run](https://drive.google.com/file/d/1uawnigtD5zGxpa5VG-PiQdWk6DqU9cnA/view)**: chapter 1 of OpenStax *Concepts of Biology* goes from PDF to an approved, styled PowerPoint deck, including both review checkpoints.

## User guide

The **[UI guide](https://claude.ai/artifact/PKysyCzwVWGjdrjnKngJVw)** walks through the screen step by step with annotated screenshots: uploading a chapter, choosing pages, setting the style, approving the outline and the deck, and building a preferences file from a PowerPoint template. A copy is kept in the repo at [`docs/ui-guide/index.html`](docs/ui-guide/index.html); open it in a browser after cloning.

| Review the outline | Download the deck |
| --- | --- |
| ![Outline ready for review with Approve and Reject buttons](docs/ui-guide/img/outline.jpg) | ![Rendered PPTX ready to approve and download](docs/ui-guide/img/deck.jpg) |

## What's new

- **Slide images.** Content images are extracted from the PDF with their page position. Decoration is dropped first: very small images and images repeated across many pages. The model picks at most one image per slide, and the renderer places it beside the bullets.
- **Page range.** Optional **First page** and **Last page** fields limit extraction to part of the PDF. Pages keep their original numbers, so `source_pages` and image ids still point at the real page.
- **Whole-page outline.** The outline step receives whole pages in one request instead of chunks.
- **Preferences file.** A JSON preferences file replaces the PPTX template for styling, and the UI can create one from an existing `.pptx` (see [Personalization](#personalization)).
- **Review flow.** The outline and deck approvals work reliably in the Gradio UI, and the status line and graph log show progress while a run is going.
- **Any OpenAI-compatible endpoint.** Set `OPENAI_BASE_URL` in `.env` to use another provider or a local server.

## Architecture

```mermaid
flowchart TD
    A[Gradio Upload + Style] --> B[validate_input]
    B --> C[extract_pdf]
    C --> E[build_outline]
    E --> F{HITL: approve outline}
    F -->|reject| E
    F -->|approve| G[map_style]
    G --> H[generate_slides]
    H --> I[render_pptx]
    I --> J[validate_artifact]
    J --> K{HITL: approve deck}
    K -->|revise| H
    K -->|approve| L[complete]
```

The LLM is responsible for semantic transformation; deterministic Python code owns PDF extraction, validation, style mapping, and PowerPoint rendering.

## Quick start

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.11–3.13 (uv downloads a matching interpreter if none is installed).

```bash
uv sync --extra dev
cp .env.example .env
# add OPENAI_API_KEY
uv run pdf2deck
```

`uv sync` creates `.venv`, installs the project in editable mode with the `dev` extra, and writes `uv.lock`. `uv run` executes inside that environment, so there is no need to activate it.

Open the Gradio URL printed by the app (usually http://127.0.0.1:7860). The [UI guide](#user-guide) covers the rest.

Development commands:

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

## Personalization

The look of the deck comes from a JSON preferences file. Every field is optional and falls back to the default shown here; an unknown field is rejected.

```json
{
  "name": "technical-minimal",
  "tone": "educational",
  "density": "balanced",
  "include_speaker_notes": true,
  "slide_size": { "width_in": 13.333, "height_in": 7.5 },
  "colors": {
    "main": "#1F4E79",
    "highlight": "#70AD47",
    "text": "#000000",
    "background": "#FFFFFF"
  },
  "fonts": { "heading": "Aptos", "body": "Aptos" },
  "type_scale": { "title_pt": 32, "body_pt": 18 }
}
```

`tone` is one of `formal`, `educational`, `executive`, `conversational`; `density` is one of `sparse`, `balanced`, `dense`. Both are passed to the model. The other fields are applied by the renderer: `main` colours titles, `highlight` the rule under them, `text` the body.

- Upload the file in the UI as the preferences file. It then sets the whole style, and the Style name, Tone, Density and Font fields are ignored.
- Without a file, those four fields set the style and the rest uses the defaults.
- `DEFAULT_PREFERENCES_PATH` names a file to use whenever none is uploaded.

### Starting from a PowerPoint template

Open **Create a preferences file from a PPTX template** in the UI, upload a `.pptx` and press **Extract preferences**. This reads the template's slide size, theme colours, theme fonts, text sizes and text density into a preferences file. Review or edit it, then upload it as the preferences file.

The template itself is not used to build the deck, so its backgrounds, artwork and layouts do not carry over.

## Production direction

- Replace `MemorySaver` with PostgreSQL-backed LangGraph persistence.
- Put generated artifacts in object storage (S3-compatible).
- Run the graph behind a queue/worker service.
- Keep Gradio as an internal/operator UI; expose an API for production clients.
- Add a render-validation service using LibreOffice/headless PowerPoint-compatible rendering for visual regression.
- Use Langfuse datasets/evaluations for content-preservation regression tests.
