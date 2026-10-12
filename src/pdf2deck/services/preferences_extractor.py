import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Literal

from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml import parse_xml
from pptx.oxml.ns import qn
from pptx.util import Emu

from ..schemas import Fonts, Palette, SlideSize, StylePreferences, TypeScale

ACCENTS = ("accent1", "accent2", "accent3", "accent4", "accent5", "accent6")
SYSTEM_COLORS = {"windowText": "000000", "window": "FFFFFF"}

# A title is the most common text size at least this many times the body size.
TITLE_RATIO = 1.5
# Median characters per slide below which a deck counts as sparse, then balanced.
SPARSE_BELOW = 250
BALANCED_BELOW = 600


class PreferencesExtractor:
    """Reads a starter StylePreferences out of an existing presentation."""

    def extract(self, path: Path) -> StylePreferences:
        try:
            return self._extract(path)
        except Exception as exc:
            # python-pptx, zipfile and lxml each raise their own errors for a broken file.
            raise ValueError(f"Could not read preferences from {path.name}: {exc}") from exc

    def _extract(self, path: Path) -> StylePreferences:
        prs = Presentation(str(path))
        master = prs.slide_masters[0]
        theme = parse_xml(master.part.part_related_by(RT.THEME).blob)
        slides = [slide._element for slide in prs.slides]

        return StylePreferences(
            name=self._name(path),
            density=self._density(slides),
            slide_size=self._slide_size(prs),
            colors=self._palette(theme, master._element, slides),
            fonts=self._fonts(theme),
            type_scale=self._type_scale(slides),
        )

    @staticmethod
    def _name(path: Path) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
        return slug[:100] or "extracted"

    @staticmethod
    def _slide_size(prs: Presentation) -> SlideSize:
        if prs.slide_width is None or prs.slide_height is None:
            return SlideSize()
        return SlideSize(
            width_in=round(Emu(prs.slide_width).inches, 2),
            height_in=round(Emu(prs.slide_height).inches, 2),
        )

    @staticmethod
    def _scheme_colors(theme) -> dict[str, str]:
        """Map theme colour slots (dk1, lt1, accent1, ...) to RRGGBB."""
        colors: dict[str, str] = {}
        scheme = theme.find(f".//{qn('a:clrScheme')}")
        for slot in scheme if scheme is not None else ():
            value = slot[0]
            hex_value = value.get("val") if value.tag == qn("a:srgbClr") else (
                value.get("lastClr") or SYSTEM_COLORS.get(value.get("val", ""))
            )
            if hex_value:
                colors[slot.tag.rpartition("}")[2]] = hex_value.upper()
        return colors

    def _palette(self, theme, master, slides: list) -> Palette:
        scheme = self._scheme_colors(theme)
        # The master maps the names shapes use (tx1, bg1) onto theme slots (dk1, lt1).
        color_map = master.find(qn("p:clrMap"))
        aliases = dict(color_map.attrib) if color_map is not None else {}

        used: Counter[str] = Counter()
        for slide in slides:
            for ref in slide.iter(qn("a:schemeClr")):
                name = ref.get("val", "")
                used[scheme.get(aliases.get(name, name), "")] += 1
            for ref in slide.iter(qn("a:srgbClr")):
                used[ref.get("val", "").upper()] += 1

        # Distinct accents by how often the slides use them; ties keep theme order.
        accents = list(dict.fromkeys(scheme[slot] for slot in ACCENTS if slot in scheme))
        ranked = sorted(accents, key=lambda color: -used[color])
        defaults = Palette()
        main = f"#{ranked[0]}" if ranked else defaults.main
        highlight = f"#{ranked[1]}" if len(ranked) > 1 else main

        text = scheme.get(aliases.get("tx1", "dk1"))
        background = scheme.get(aliases.get("bg1", "lt1"))
        return Palette(
            main=main,
            highlight=highlight,
            text=f"#{text}" if text else defaults.text,
            background=f"#{background}" if background else defaults.background,
        )

    @staticmethod
    def _fonts(theme) -> Fonts:
        defaults = Fonts()
        scheme = theme.find(f".//{qn('a:fontScheme')}")

        def typeface(kind: str, default: str) -> str:
            latin = scheme.find(f"{qn(kind)}/{qn('a:latin')}") if scheme is not None else None
            return (latin.get("typeface") if latin is not None else "") or default

        return Fonts(
            heading=typeface("a:majorFont", defaults.heading),
            body=typeface("a:minorFont", defaults.body),
        )

    @staticmethod
    def _type_scale(slides: list) -> TypeScale:
        sizes: Counter[float] = Counter()
        for slide in slides:
            for run in slide.iter(qn("a:rPr")):
                if run.get("sz"):
                    # Sizes are stored in hundredths of a point.
                    sizes[min(max(int(run.get("sz")) / 100, 6), 200)] += 1
        if not sizes:
            return TypeScale()

        defaults = TypeScale()
        body = sizes.most_common(1)[0][0]
        titles = [size for size, _ in sizes.most_common() if size >= body * TITLE_RATIO]
        title = titles[0] if titles else min(body * defaults.title_pt / defaults.body_pt, 200)
        return TypeScale(title_pt=round(title, 1), body_pt=body)

    @staticmethod
    def _density(slides: list) -> Literal["sparse", "balanced", "dense"]:
        if not slides:
            return StylePreferences().density
        characters = median(
            sum(len(text.text or "") for text in slide.iter(qn("a:t"))) for slide in slides
        )
        if characters < SPARSE_BELOW:
            return "sparse"
        return "balanced" if characters < BALANCED_BELOW else "dense"
