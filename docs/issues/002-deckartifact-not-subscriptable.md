# 002: Approving a review crashes with `'DeckArtifact' object is not subscriptable`

- **Status:** Fixed in the working tree, not yet committed
- **Found:** 2026-10-11
- **Area:** `src/pdf2deck/app.py`

## Symptom

Pressing an approve button raised:

```
File "src/pdf2deck/app.py", line 71, in resume_deck
    yield log, artifact["path"] if artifact else None
TypeError: 'DeckArtifact' object is not subscriptable
```

The deck file had been written to `outputs/`, but the UI showed an error and no download.

## Cause

`graph.invoke(...)` returns the state values as the pydantic models from `schemas.py`, so `result["artifact"]` is a `DeckArtifact`, not a dict. Both `resume_outline` and `resume_deck` indexed it with `artifact["path"]`. The crash therefore happened on the first resume that ran past `render_pptx`, whichever button triggered it.

## Fix

The UI now reads state values as models (`artifact.path`, `artifact.slide_count`, `event.message`). All handlers build their output through one `_view` helper, so there is a single place that touches the state shape.

## Verification

`tests/test_app_flow.py::test_approving_outline_then_deck_returns_the_pptx` runs generate → approve outline → approve deck and asserts the returned PPTX path exists.
