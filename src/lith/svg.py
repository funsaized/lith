"""Deterministic family B text posters; no provider, font download or rasterizer."""

from __future__ import annotations

import math
from xml.etree import ElementTree as ET

from .recipe import Recipe, validate_brief


def _wrap(value: str, columns: int) -> list[str]:
    """Prefer space boundaries, preserving every character including whitespace."""
    lines = []
    start = 0
    while len(value) - start > columns:
        boundary = value.rfind(" ", start, start + columns) + 1
        boundary = boundary if boundary > start else start + columns
        lines.append(value[start:boundary])
        start = boundary
    lines.append(value[start:])
    return lines


def render_svg(recipe: Recipe) -> bytes:
    """Render a standalone stacked SVG, rejecting content that cannot fit.

    Exact copy means the concatenated tspans of each data-copy element equal
    its authored value. Glyph appearance still depends on the viewer's fonts.
    The model and candidate count have no effect on this offline artifact.
    """
    brief = validate_brief(recipe.brief)
    if recipe.style != "B":
        raise ValueError("deterministic SVG supports only family B")
    unsupported = brief.keys() - {
        "topic", "headline", "title", "subtitle", "icon", "aspect", "layout",
        "sections", "footer", "prompt_mode",
    }
    if unsupported:
        raise ValueError("deterministic SVG does not support: " + ", ".join(sorted(unsupported)))
    if brief.get("layout", "stack") != "stack":
        raise ValueError("deterministic SVG supports only layout 'stack'")
    if brief.get("prompt_mode", "standard") != "standard":
        raise ValueError("deterministic SVG requires standard prompt_mode")
    aspect = brief.get("aspect")
    if aspect in (None, "auto"):
        aspect = "2:3" if len(brief.get("sections", [])) >= 3 else "1:1"
    if aspect not in {"1:1", "2:3", "3:2"}:
        raise ValueError("deterministic SVG supports aspects 1:1, 2:3 and 3:2")
    numerator, denominator = map(int, aspect.split(":"))
    width, height = 1200, 1200 * denominator // numerator
    root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg",
                             "width": str(width), "height": str(height),
                             "viewBox": f"0 0 {width} {height}", "xml:space": "preserve"})

    def rect(x, y, w, h, fill, stroke="none"):
        ET.SubElement(root, "rect", dict(x=str(x), y=str(y), width=str(w), height=str(h),
                                        fill=fill, stroke=stroke))

    def text(value, key, x, top, font_size, color, available):
        if any(ord(char) < 32 or ord(char) > 126 for char in value):
            raise ValueError(f"{key}: deterministic SVG requires printable ASCII (no tabs/newlines)")
        # SVG textLength fixes the advance width even when monospace resolves
        # to a different installed font. Never squeeze copy to fit vertically.
        advance = font_size * 0.62
        lines = _wrap(value, math.floor(available / advance))
        line_height = math.ceil(font_size * 1.4)
        node = ET.SubElement(root, "text", {"data-copy": key, "fill": color,
                             "font-family": "monospace", "font-size": str(font_size),
                             "style": "white-space:pre;font-variant-ligatures:none"})
        for index, line in enumerate(lines):
            span = ET.SubElement(node, "tspan", {"x": str(x), "y": str(top + font_size + index * line_height),
                                 "textLength": f"{len(line) * advance:.2f}", "lengthAdjust": "spacingAndGlyphs"})
            span.text = line
        return top + len(lines) * line_height

    rect(0, 0, width, height, "#000000")
    title_key = "title" if "title" in brief else "headline"
    y = text(brief[title_key], title_key, 48, 40, 52, "#FFFFFF", 1104) + 12
    if "subtitle" in brief:
        y = text(brief["subtitle"], "subtitle", 48, y, 24, "#00E5FF", 1104) + 20
    for index, section in enumerate(brief.get("sections", [])):
        if section.keys() - {"heading", "lines"}:
            raise ValueError(f"sections/{index}: only heading and lines are supported")
        # Background is inserted before its text, with height filled in after layout.
        panel = ET.SubElement(root, "rect", {"x": "48", "y": str(y), "width": "1104",
                                            "fill": "#000000", "stroke": "#00E5FF"})
        start = y
        y = text(section["heading"], f"sections/{index}/heading", 68, y + 14, 28, "#00E5FF", 1064) + 10
        for line_index, line in enumerate(section.get("lines", [])):
            rect(70, y + 10, 7, 7, "#FF3030")
            y = text(line, f"sections/{index}/lines/{line_index}", 92, y, 22, "#00E5FF", 1040) + 6
        y += 12
        panel.set("height", str(y - start))
        y += 20
    if "footer" in brief:
        rect(48, y, 1104, 2, "#00E5FF")
        y = text(brief["footer"], "footer", 48, y + 14, 22, "#00E5FF", 1104)
    if y > height - 40:
        raise ValueError(f"deterministic SVG copy needs {y + 40}px height; frame is {height}px. "
                         "Choose a taller supported aspect or revise the authored copy; nothing was published")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
