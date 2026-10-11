# 001: Outline and generated deck never appear in the UI

- **Status:** Fixed in the working tree, not yet committed
- **Found:** 2026-10-11
- **Area:** `src/pdf2deck/app.py`

## Symptom

After uploading a PDF and pressing **Generate**, only the "Graph execution" box filled in. No outline was shown for review, and the "PPTX output" slot stayed empty for the whole run.

## Cause

Two separate gaps in the UI:

1. There was no outline component. The outline only existed inside the `__interrupt__` payload, which was dumped into the log with `json.dumps(..., default=str)` as one long unreadable string, next to the full extracted PDF text.
2. `run_deck` always yielded `None` for the PPTX output. The only code that could set it was in the resume handlers, which crashed before returning (see [002](002-deckartifact-not-subscriptable.md)).

## Fix

- Added an outline panel that renders the `DeckOutline` as markdown: title, subtitle, learning objectives, then each slide with its layout type, purpose and key points.
- The PPTX path is now returned as soon as the deck is rendered, so it can be downloaded before the deck review, and it stays after approval.
- Added a status line that says what the run is waiting for.
- "Graph execution" now shows one line per step (`[completed] extract_pdf: Extracted 11 pages into 11 chunks.`) instead of the JSON dump.

## Verification

`tests/test_app_flow.py::test_generate_shows_outline_and_waits_for_outline_review` and `::test_approving_outline_then_deck_returns_the_pptx`. Also checked over HTTP against the running Gradio app with a stubbed model and a real PDF. The page was not inspected in a browser.
