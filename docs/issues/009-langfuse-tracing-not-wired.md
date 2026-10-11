# 009: Langfuse tracing is never activated

- **Status:** Open
- **Found:** 2026-10-11
- **Area:** `src/pdf2deck/observability.py`, `src/pdf2deck/app.py`

## Problem

Runs produce no Langfuse traces, even with `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` set.

`observability.langfuse_context` builds the callback handler and trace attributes, but nothing calls it. The app streams the graph with only a `thread_id` in its config, so no callbacks reach the graph or the model call.

The docs describe tracing as present (`docs/operations_guidelines.md` section 2, and `observability.py` listed as the "Langfuse boundary" in `docs/implementation_guidelines.md`).

## Impact

The only record of a run is the console log added for [005](005-run-looks-stuck-during-outline-generation.md): step names and durations. Prompts, model outputs and token usage are not recorded anywhere, which also blocks the investigation in [006](006-outline-generation-latency.md).

## Suggested direction

In `app._drive`, wrap the `graph.stream(...)` loop in `langfuse_context(settings, run_id)` and add the returned `callbacks` to the run config. Things to check when doing it:

- A run spans several Gradio requests (generate, approve outline, approve deck). Each one would open its own context; they should share `session_id=run_id`, which the helper already sets.
- `langfuse_context` wraps its whole body in `try/except Exception`. An exception raised by the graph inside the `with` block would be caught there and followed by a second `yield`, which makes the context manager raise `RuntimeError`. The error handling needs to be narrowed to the Langfuse setup before the helper is used around graph execution.
