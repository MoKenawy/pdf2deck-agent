# 004: LangGraph warns about unregistered checkpoint types

- **Status:** Fixed in the working tree, not yet committed
- **Found:** 2026-10-11
- **Area:** `src/pdf2deck/graph.py`

## Symptom

On every resumed run the console printed, once per type:

```
Deserializing unregistered type pdf2deck.schemas.SourceDocument from checkpoint.
This will be blocked in a future version. Set LANGGRAPH_STRICT_MSGPACK=true to
block now, or add to allowed_msgpack_modules to allow explicitly: ...
```

The same appeared for `DeckOutline`, `ExecutionEvent`, `StyledSlide` and `DeckArtifact`.

## Cause

The checkpointer was created as `InMemorySaver()` with the default serializer. That serializer restores any pydantic model it finds in a checkpoint but warns that this permissive behaviour will be removed. Once it is, resumed runs would no longer get their state back as models.

## Fix

`DeckGraph.build` now passes `InMemorySaver` a `JsonPlusSerializer` whose `allowed_msgpack_modules` lists every direct subclass of `schemas.StrictModel`.

## Things to know

- With an explicit allowlist the serializer blocks anything not on it instead of warning. A new state model must subclass `StrictModel` directly, or be added to the list, or it will not be restored on resume.
- The warning is emitted once per type per process, so it cannot be asserted reliably in a test. The flow tests cover it indirectly: they read restored models after a resume and would fail if one were blocked.
- The same serializer setting is needed when `InMemorySaver` is replaced by a PostgreSQL checkpointer.
