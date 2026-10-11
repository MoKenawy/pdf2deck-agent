# 003: "Approve deck" approves the outline (review buttons are interchangeable)

- **Status:** Fixed in the working tree, not yet committed
- **Found:** 2026-10-11
- **Area:** `src/pdf2deck/app.py`, `src/pdf2deck/graph.py`

## Symptom

Pressing **Approve deck** while the run was still waiting for the outline review approved the outline and rendered the deck. Nothing was reviewed. This is how [002](002-deckartifact-not-subscriptable.md) was first hit: the outline was not visible ([001](001-outline-and-deck-not-shown-in-ui.md)), so "Approve deck" looked like the next step.

## Cause

`resume_outline` and `resume_deck` were identical. Each sent `Command(resume={"approved": ...})` to the thread, and LangGraph applies a resume to whichever interrupt is pending. All four review buttons were always enabled.

## Fix

- The two checkpoints are named in `graph.py` (`OUTLINE_REVIEW`, `DECK_REVIEW`) and carried in each interrupt payload.
- Before resuming, the handler reads the pending interrupt from `graph.get_state(...)` and raises "No deck is waiting for review." (or "No outline…") if it does not match.
- Each pair of buttons is enabled only while its own review is pending.

## Verification

`tests/test_app_flow.py::test_deck_review_cannot_resume_a_pending_outline_review`, plus the button-state assertions in the other flow tests.
