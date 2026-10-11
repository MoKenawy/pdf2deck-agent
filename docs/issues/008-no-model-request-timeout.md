# 008: Model requests have no configured timeout

- **Status:** Open
- **Found:** 2026-10-11
- **Area:** `src/pdf2deck/services/llm_service.py`, `src/pdf2deck/config.py`

## Problem

`LlmService` builds `ChatOpenAI` without `timeout` or `max_retries`, so the OpenAI client defaults apply: a 600-second timeout per request and 2 retries. A request that never answers can hold a run for about 30 minutes before it fails.

This has not been observed. The slow runs seen so far all completed (see [006](006-outline-generation-latency.md)). It is listed because the operations checklist in `docs/operations_guidelines.md` has "model timeout configured" unchecked, and because a real hang would be indistinguishable from a slow run for a long time.

## Constraint

A legitimate outline call took 261 seconds. A timeout below that would fail good runs, and each retry repeats the whole call.

## Suggested direction

- Add `MODEL_TIMEOUT_SECONDS` and `MODEL_MAX_RETRIES` to `Settings` and pass them to `ChatOpenAI`.
- Pick the default after the latency in [006](006-outline-generation-latency.md) is understood. Until then, something like 420 seconds with 1 retry bounds a hang at 14 minutes without cutting off the slowest run seen.
- A timeout already surfaces correctly in the UI: it is reported as "**Failed:** …" (see [005](005-run-looks-stuck-during-outline-generation.md)).
