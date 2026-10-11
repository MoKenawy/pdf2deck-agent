# 005: Run looks stuck on "Running…" with no trace of what it is doing

- **Status:** Fixed in the working tree, not yet committed
- **Found:** 2026-10-11
- **Area:** `src/pdf2deck/app.py`

## Symptom

After pressing **Generate** the page showed "Running…" and an empty outline for minutes. The terminal printed nothing. It was impossible to tell a slow run from a hung one.

## Cause

The run was not hung. It was waiting on the model call in `build_outline`, which took between 43 and 261 seconds in three measured runs (see [006](006-outline-generation-latency.md)). Three things hid that:

1. The UI streamed with `stream_mode="updates"`, which only emits when a node finishes. Nothing was sent while the slow node was running.
2. The app logged nothing to the console.
3. Only `ValueError` was handled. Any other exception (model API error, rendering bug) left the last "Running…" status on screen.

## Fix

- The UI now streams `["tasks", "updates"]` and reacts to task-start events. The status line names the running step, for example "Generating the outline with `<model>`… this is the slow step and can take several minutes".
- "Graph execution" adds a `[started] <node>: running…` line while a step runs and a `[waiting] <checkpoint>` line when a review is pending.
- `main()` configures logging. The console prints each step's start and duration per run, and the OpenAI client's request retries:

  ```
  INFO pdf2deck.app: run 63ff…: build_outline started
  INFO pdf2deck.app: run 63ff…: build_outline finished in 62.5s
  INFO pdf2deck.app: run 63ff…: waiting for outline_review
  ```

- Unexpected exceptions are logged with a traceback and shown as "**Failed:** `<type>`: `<message>`". Expected stops (`ValueError`: bad input, rejected review) show as "**Stopped:** …".

## Verification

`tests/test_app_flow.py::test_generate_reports_the_running_step_before_it_finishes` and `::test_model_failure_is_reported_instead_of_leaving_the_run_spinning`. Also confirmed over HTTP, with a model stub that sleeps, that the "Generating the outline…" status reaches the client before the call returns.
