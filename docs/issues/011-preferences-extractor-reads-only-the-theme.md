# 011: The preferences extractor returns the same Office colours and fonts for every PPTX

- **Status:** Fixed
- **Found:** 2026-10-15, fixed 2026-10-15
- **Area:** `src/pdf2deck/services/preferences_extractor.py`
- **GitHub:** [#7](https://github.com/MoKenawy/pdf2deck-agent/issues/7)

## Symptom

**Extract preferences** gave `main #4F81BD`, `highlight #C0504D`, `text #000000`, `background #FFFFFF` and Calibri for every template tried. Only the type scale changed between decks. For `Introduction to Biology.pptx` (a Gemini deck in green and slate, set in Plus Jakarta Sans) that is the wrong palette and the wrong font. The renderer applied the JSON correctly, so the deck came out in stock Office colours.

## Cause

The extractor read colours and fonts from the theme. python-pptx, Gemini and most other generators ship the stock Office theme and set their real styling directly on each slide.

- `main` and `highlight` could only be theme accents. Slide colours were counted, but only to rank the six accents.
- Every autoshape has a `<p:style>` block naming `accent1` three times (`lnRef`, `fillRef`, `effectRef`), even when its own fill overrides it. Those references were counted as uses, so `accent1` always came first. All 120 `schemeClr` references on the Biology slides sit inside `<p:style>`.
- `text`, `background` and the fonts came from the theme only.

## Fix

The extractor now reads what the slides use, by the role the renderer gives each value. The theme is the fallback for a deck that sets nothing directly.

- **Colours** are read only from direct formatting: run colours, shape and table-cell fills, lines and slide backgrounds. `<p:style>` is skipped. Scheme colours are resolved through the master's `clrMap`.
- A colour counts as a brand colour (vivid) when its channels spread by at least 64 of 255. Greys, slates and pale tints do not.
- `main` is the vivid colour used most on titles, else the vivid colour the slides use most. `highlight` is the next vivid colour. With no vivid colours, the theme accents are ranked as before. With only one, `highlight` repeats `main` rather than falling back to a stock accent.
- `text` is the most common non-vivid body text colour. Text without its own colour counts as the theme's text colour.
- `background` is the most common solid slide background, inherited from the layout and then the master.
- **Fonts:** `heading` is the typeface used most on title text, `body` the one used most on body text. `+mj-lt`/`+mn-lt` and runs without a typeface resolve to the theme fonts.
- **Title text** is text in a title placeholder, or at least 1.5 times the body size (the same rule the type scale uses).

## Things to know

- Colour transforms (`lumMod`, `tint`, …) are ignored, as before.
- Gradient and picture backgrounds give no vote. A deck that uses only those falls back to the theme's background.
- The Biology deck's titles are dark slate. `main` takes the brand green instead, because a neutral title colour is not counted as a brand colour.
- `highlight` is the second most used vivid colour, which can be a shade of `main` (Biology gives `#10B981` next to `#059669`). Review it before use.
- The UI guide screenshot `docs/ui-guide/img/json.jpg` still shows the old output.

## Verification

- `tests/test_preferences_extractor.py`:
  - A deck rendered by `PptxService` is extracted back to the preferences it was drawn from: colours, fonts, type scale and slide size.
  - Colours and fonts set directly on the slides win over the theme, and the autoshapes' `<p:style>` does not count.
  - The theme fallback tests still pass.
- Extracting the decks in `tests/`:
  - `Introduction to Biology.pptx`: main `#059669`, highlight `#10B981`, text `#475569`, background `#FFFFFF`, Plus Jakarta Sans, title 27 pt, body 12 pt.
  - The two pdf2deck outputs return the preferences they were rendered from: `#4FBD8B`/`#348B64` Calibri 27/12, and `#1F4E79`/`#70AD47` Aptos 32/18.
