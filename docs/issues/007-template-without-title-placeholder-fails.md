# 007: Personalization was tied to a PPTX render base; it is now a JSON preferences file

- **Status:** Fixed in the working tree, not yet committed
- **Found:** 2026-10-11, respecified and fixed 2026-10-12
- **Area:** `src/pdf2deck/schemas.py`, `src/pdf2deck/preferences.py`, `src/pdf2deck/app.py`, `src/pdf2deck/services/pptx_service.py`, `src/pdf2deck/services/preferences_extractor.py`

## Symptom

With `Creative-Idea-Bulb-PowerPoint-Template.pptx` uploaded as the template, approving the outline ended the run with:

```
Failed: AttributeError: 'NoneType' object has no attribute 'text'
```

raised from `PptxService.render` at `title.shapes.title.text = outline.title`. No deck was produced. Without a template, rendering worked. Reproduced with a stubbed model, so no outline content was involved.

## Cause

The renderer opened the uploaded `.pptx`, deleted its slides and added new ones on its layouts. It assumed every layout has a title placeholder and picked layouts by fixed index (0, 1, 3), the layout order of the default python-pptx template.

This template has 19 layouts over three slide masters (`prs.slide_layouts` returns only the first master's two). None has a title placeholder, because the template uses body placeholders for its titles. Selecting layouts by placeholder type would not have fixed it.

The crash exposed a specification problem. A template is not a known input: its layouts, placeholders and masters differ from file to file, and the renderer had to guess at them. The renderer is a deterministic tool, so the user's visual preferences should reach it as typed values. In addition, `StylePreferences.primary_color` and `accent_color` were never read, and the UI's Font box overrode the template's own font.

## Decisions (2026-10-12)

1. **Format.** Personalization is a JSON file holding `StylePreferences`. The renderer takes typed values, not prose and not a presentation.
2. **Not a graph stage.** The file is loaded and validated when the run is created. No node was added.
3. **Extractor.** A `.pptx` is a source for a starter preferences file. The extractor ships in this version and is invoked by a button in the UI.
4. **File and UI form.** An uploaded file wins and the form says so; without a file, the form works as before.
5. **Steering the LLM beyond tone and density.** Not in this version. When added, it is a typed field with fixed values, not free text, which keeps guidelines principle 2 and §8 (the LLM proposes content structure only) intact.

## Fix

- **Schema.** `StylePreferences` keeps `name`, `tone`, `density` and `include_speaker_notes`, and gains `slide_size`, `colors` (main, highlight, text, background), `fonts` (heading, body) and `type_scale` (title, body). `template_path`, `primary_color`, `accent_color` and `font_family` are gone. Unknown fields and colours that are not `#RRGGBB` are rejected. The README documents the file.
- **Loader.** `load_preferences` reads the file and, when it does not validate, names every invalid field.
- **Renderer.** `PptxService` always starts from a clean presentation, sets the slide size, and draws each slide on the blank layout from the preferences: background, title in the main colour, a rule in the highlight colour, bulleted body. It no longer touches layouts or placeholders of a user's file, so the crash cannot occur.
- **Extractor.** `PreferencesExtractor` reads slide size, theme colours (ranked by how often the slides use them), theme fonts, the common text sizes and text density from a `.pptx`.
- **UI.** The template upload became a preferences file upload. A bad file stops the run with the field named, before the outline call. The Style name, Tone, Density and Font fields lock while a file is in use. **Create a preferences file from a PPTX template** holds the template upload, the **Extract preferences** button, a preview and a download.
- **Settings.** `DEFAULT_TEMPLATE_PATH` became `DEFAULT_PREFERENCES_PATH`: a preferences file to use when none is uploaded.

## Things to know

- A template's backgrounds, artwork and layouts do not carry over. The deck follows the template's palette and typography without looking like it. For the bulb template that means its nine images and its infographic composition are not reproduced.
- The extractor cannot read "feel", and it leaves `tone` at the default.
- The extracted type scale is a heuristic: body is the most common explicit text size, title the most common size at least 1.5 times larger. Review it before use.
- Body text size now comes from `type_scale.body_pt`. It used to be 22 pt for sparse decks and 18 pt otherwise.
- Every `visual_type` is still drawn as a title with bullets.
- An existing `.env` that sets `DEFAULT_TEMPLATE_PATH` is not an error; the setting is ignored.

## Verification

- `tests/test_schemas.py`, `tests/test_preferences.py`, `tests/test_pptx_service.py` and `tests/test_preferences_extractor.py` cover the schema, the loader, the renderer and the extractor.
- `tests/test_app_flow.py` covers precedence (uploaded file, then the default file, then the form), the early stop on an invalid file, the field lock and the extract handler.
- Extracting from `Creative-Idea-Bulb-PowerPoint-Template.pptx` gives 10 x 5.62 in, main `#32AEB8`, highlight `#F2A40D`, Arial, title 24 pt, body 12 pt, density balanced. A deck rendered from that file opens in PowerPoint without a repair prompt.
- Not yet checked in a running Gradio UI: the new upload, the accordion and the field lock on screen.
