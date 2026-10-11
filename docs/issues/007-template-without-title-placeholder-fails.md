# 007: Rendering fails for templates whose layouts have no title placeholder

- **Status:** Open
- **Found:** 2026-10-11
- **Area:** `src/pdf2deck/services/pptx_service.py`

## Symptom

With `Creative-Idea-Bulb-PowerPoint-Template.pptx` uploaded as the template, approving the outline ends the run with:

```
Failed: AttributeError: 'NoneType' object has no attribute 'text'
```

raised from `PptxService.render` at `title.shapes.title.text = outline.title`. No deck is produced. Without a template, rendering works.

Reproduced with a stubbed model, so no outline content is involved.

## Cause

The renderer assumes every layout it uses has a title placeholder:

- `render` sets `title.shapes.title.text` on a slide built from `slide_layouts[0]`.
- `_render_slide` sets `slide.shapes.title.text` on every content slide.

`slide.shapes.title` is `None` when the layout has no title placeholder. This template has only two layouts, "Cover Slide layout" and "End Slide Layout", each with two body placeholders and no title. Its 37 designed slides carry the visual design directly, not through layouts.

`_layout` also picks layouts by fixed index (0, 1, 3), which assumes the layout order of the default python-pptx template.

## Decision needed

How should a template like this be used? Options:

1. **Reject it early.** Validate the template when the run starts and stop with a clear message ("template has no layout with a title placeholder") before the slow outline call.
2. **Degrade gracefully.** When a layout has no title placeholder, write the title into the first text placeholder or a text box. The deck renders, but every slide uses the cover layout, so the result will not look like the template's designed slides.
3. **Use the template's slides as the designs.** Map each `visual_type` to one of the template's existing slides and clone it. This is the only option that reproduces the template's look, and it is a larger change to the renderer.

Option 1 is the smallest change that removes the confusing failure. Whichever is chosen, `_layout` should select layouts by placeholder type, not by index.
