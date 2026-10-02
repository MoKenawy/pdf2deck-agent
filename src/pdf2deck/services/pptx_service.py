from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

from ..schemas import DeckArtifact, DeckOutline, StylePreferences, StyledSlide


class PptxService:
    def _load_base(self, template_path: str | None) -> Presentation:
        prs = Presentation(template_path) if template_path else Presentation()
        # Keep the presentation theme/master/layouts but remove existing content slides.
        for slide in list(prs.slides):
            r_id = slide.slide_id
            slide_id = prs.slides._sldIdLst[0].rId if prs.slides._sldIdLst else None
            # Public API has no remove-slide operation; use the supported underlying
            # presentation XML collection in this controlled renderer boundary.
            for sldId in prs.slides._sldIdLst:
                if int(sldId.id) == r_id:
                    prs.part.drop_rel(sldId.rId)
                    prs.slides._sldIdLst.remove(sldId)
                    break
        return prs

    def render(
        self,
        outline: DeckOutline,
        styled_slides: list[StyledSlide],
        style: StylePreferences,
        output_path: Path,
    ) -> DeckArtifact:
        prs = self._load_base(style.template_path)

        title = prs.slides.add_slide(prs.slide_layouts[0])
        title.shapes.title.text = outline.title
        if len(title.placeholders) > 1:
            title.placeholders[1].text = outline.subtitle or "Generated from source chapter"

        for styled in styled_slides:
            slide = prs.slides.add_slide(self._layout(prs, styled.layout_name))
            self._render_slide(slide, styled, style)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(output_path)
        return DeckArtifact(
            path=str(output_path),
            slide_count=len(prs.slides),
            title=outline.title,
        )

    def _layout(self, prs: Presentation, name: str):
        if name == "title":
            return prs.slide_layouts[0]
        if name == "comparison" and len(prs.slide_layouts) > 3:
            return prs.slide_layouts[3]
        return prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]

    def _render_slide(
        self,
        slide,
        styled: StyledSlide,
        style: StylePreferences,
    ) -> None:
        plan = styled.plan
        slide.shapes.title.text = plan.title

        body = None
        for shape in slide.placeholders:
            if shape.placeholder_format.idx != 0 and hasattr(shape, "text_frame"):
                body = shape
                break

        if body is None:
            box = slide.shapes.add_textbox(
                Inches(0.8), Inches(1.7), Inches(11.7), Inches(4.8)
            )
            body = box

        tf = body.text_frame
        tf.clear()
        for index, point in enumerate(plan.key_points):
            p = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
            p.text = point
            p.font.size = Pt(22 if style.density == "sparse" else 18)
            p.font.name = style.font_family

        if style.include_speaker_notes and plan.speaker_notes:
            try:
                notes = slide.notes_slide.notes_text_frame
                notes.text = plan.speaker_notes
            except Exception:
                # Notes support varies by python-pptx version/template.
                pass
