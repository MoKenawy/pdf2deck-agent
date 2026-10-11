# 006: Outline generation is slow and its duration varies widely

- **Status:** Open, cause not identified
- **Found:** 2026-10-11
- **Area:** `src/pdf2deck/services/llm_service.py`, `src/pdf2deck/prompts.py`

## Symptom

`build_outline` dominates the run time and is unpredictable. Three runs of the same input on the same configuration:

| Run | `build_outline` duration |
| --- | --- |
| 1 | 261 s |
| 2 | 43 s |
| 3 | 62 s |

Input: `tests/EJ1172284.pdf` (11 pages, 11 chunks, about 42,000 prompt characters). Model: `gemini-3.8-flash` through the OpenAI-compatible endpoint, temperature 0.1, `MAX_SLIDES=30`. Every other step finishes in under a second.

## What is known

- Run 3 logged no client-side retries, so its time was a single request.
- Output length does not explain the gap. Runs 1 and 3 produced outlines of nearly the same size (9,753 and 9,851 characters as rendered markdown). Run 2 returned 18 slides.
- The endpoint returned no token usage for the one call where it was checked (run 2, a streamed call), so output and reasoning token counts are unknown.
- Run 1 predates the console logging added for [005](005-run-looks-stuck-during-outline-generation.md), so it is not known whether it included retries.

## Not yet tested

- Whether the long run was client retries or time spent on the model side.
- Whether a lower `MAX_SLIDES`, a reasoning-effort setting, or a different structured-output method shortens the call.

## Suggested next steps

1. Run several times with the new console logging and note duration and retries per run.
2. Record token usage per call if the endpoint can return it.
3. If retries are the cause, look at the error they follow (rate limit, overload) before changing the prompt or model settings.
4. Decide on a request timeout once a normal upper bound is known (see [008](008-no-model-request-timeout.md)).
