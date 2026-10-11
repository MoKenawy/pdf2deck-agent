# 010: Rejecting a review ends the run; the README shows revision loops that do not exist

- **Status:** Open (known MVP limitation, documentation out of step)
- **Found:** 2026-10-11
- **Area:** `src/pdf2deck/graph.py`, `README.md`

## Problem

**Reject outline** and **Reject deck** terminate the run. `approve_outline` and `approve_deck` raise `ValueError` when `approved` is false, and there is no edge back to an earlier node. To try again the user has to press **Generate**, which repeats the slow outline call (see [006](006-outline-generation-latency.md)).

The UI now reports this as "**Stopped:** Outline was rejected. Restart the run after revising style/input." instead of a traceback, but the behaviour is unchanged.

## Documentation mismatch

The architecture diagram in `README.md` shows:

- `reject` on the outline review looping back to `build_outline`,
- `revise` on the deck review looping back to `generate_slides`,
- nodes `chunk_document` and `generate_slides`.

None of these exist in `DeckGraph.build`. The graph is a straight line of eight nodes, and chunking happens inside `extract_pdf`.

`docs/implementation_guidelines.md` does state that the MVP terminates on rejection, and `docs/adrs/ADR-003-hitl.md` lists a bounded revision policy as future work. `LlmService.revise_outline` and `REVISION_SYSTEM` exist but are not called.

## Suggested direction

- Short term: correct the README diagram to match the graph.
- Then: implement the outline revision loop. Let the reviewer attach a comment to a rejection, route `approve_outline` back to a revision node that calls `revise_outline`, and cap the number of rounds as ADR-003 requires. Reject would then need a text input in the UI.
