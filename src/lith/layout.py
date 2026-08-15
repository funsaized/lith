"""Zone and arrangement vocabulary for spec-driven posters.

Two rules shape everything here:

*Nothing in this module may read like content.* The layout block sits in the
same prompt as the verbatim-copy order, so any phrase that looks like a
heading gets drawn as one. Zone notes are lowercase prose, never labels.

*The copy block stays purely literal.* A diagram is described, not quoted, so
its description belongs here among the instructions rather than in the block
the model is told to reproduce character for character.
"""

from __future__ import annotations

from typing import Any

# How a set of section panels is arranged. Each value completes the phrase
# "the N section panels, <arrangement>, each with its heading ...".
ARRANGEMENTS: dict[str, str] = {
    "stack": "in a single full-width column, one panel per row",
    "two-column": "in two balanced columns",
    "three-column": "in three balanced columns",
    "grid-2x2": "in a strict 2-wide, 2-tall grid",
    "grid-2x3": "in a strict 2-wide, 3-tall grid",
    "grid-3x2": "in a strict 3-wide, 2-tall grid",
    "grid-3x3": "in a strict 3-wide, 3-tall grid",
    "hero": (
        "with the first panel spanning the full width at roughly double height "
        "as the anchor of the composition, and the rest in a balanced grid "
        "beneath it"
    ),
    "sidebar": (
        "with the first panel as a tall narrow rail down the left edge, full "
        "height, and the rest stacked in a wider column to its right"
    ),
    "timeline": (
        "as a top-to-bottom sequence joined by one continuous vertical spine, "
        "each panel connected to the spine by a short horizontal stub and set "
        "slightly further right than the one above it"
    ),
    "radial": (
        "spaced evenly around the diagram at the centre of the frame, each "
        "joined to it by a thin leader line"
    ),
    "masonry": (
        "in two columns of deliberately unequal height, staggered so no two "
        "panel tops align, in the manner of a magazine spread"
    ),
    "zigzag": (
        "in a hard left-right zigzag, never in columns: each panel shoved "
        "fully against one edge of the frame and the next shoved fully "
        "against the opposite edge, so consecutive panels barely overlap "
        "horizontally and the eye is thrown side to side down the page. Tilt "
        "each panel 6-10 degrees, alternating the direction of tilt, and run "
        "a bold connector line diagonally from the lower corner of each panel "
        "to the upper corner of the next. The ragged margin this leaves is "
        "the point — do not straighten or balance it"
    ),
    "split": (
        "as two facing groups divided by one strong vertical rule down the "
        "centre, the left group reading against the right"
    ),
    "diagonal": (
        "stepping down the frame from upper left to lower right, each panel "
        "overlapping the corner of the last, edges kept parallel"
    ),
}

# Where the diagram sits relative to the panels.
DIAGRAM_POSITIONS: dict[str, str] = {
    "below": "full width beneath the section panels",
    "above": "full width between the title and the section panels",
    "beside": "filling the right half of the frame, level with the section panels",
    "center": "at the centre of the frame with the section panels around it",
}

# Arrangements that only make sense with the diagram in the middle.
_CENTRED = {"radial"}


def _auto_arrangement(count: int, landscape: bool) -> str:
    """Pick an arrangement from panel count and the shape of the frame.

    Column counts are capped at two in portrait: three narrow columns of body
    copy in a tall frame is where legibility goes first.
    """
    if count <= 1:
        return "stack"
    if count == 2:
        return "two-column"
    if count == 3:
        return "three-column" if landscape else "hero"
    if count == 4:
        return "grid-2x2"
    if count == 5:
        return "hero"
    if count == 6:
        return "grid-3x2" if landscape else "grid-2x3"
    if count <= 9:
        return "grid-3x3" if landscape else "two-column"
    return "two-column"


def resolve_arrangement(
    brief: dict[str, Any], count: int, landscape: bool = False
) -> str:
    """The arrangement key for this brief: explicit if given, else derived."""
    requested = brief.get("layout")
    if not requested:
        return _auto_arrangement(count, landscape)
    if requested not in ARRANGEMENTS:
        raise ValueError(
            f"unknown layout {requested!r}; choose one of "
            f"{', '.join(sorted(ARRANGEMENTS))}"
        )
    return requested


def format_layout(brief: dict[str, Any], landscape: bool = False) -> str:
    """Describe only the zones the brief actually has copy for.

    An unconditional skeleton contradicts the verbatim-copy rule: ordered to
    draw a section grid with no sections to put in it, the model invents
    filler. Zones track the spec so sparse and dense briefs both work.
    """
    sections = brief.get("sections", [])
    if sections:
        title_size = "12-15% of frame height"
    else:
        # No body copy to compete with, so the title carries the whole poster.
        title_size = "30-40% of frame height, dominating the composition"
    title = f"the title, set at {title_size}"
    if brief.get("subtitle"):
        title += ", with the subtitle centred beneath it at half that size"
    zones = [title]

    arrangement = None
    if sections:
        count = len(sections)
        arrangement = resolve_arrangement(brief, count, landscape)
        widest = max(len(s.get("lines", [])) for s in sections)
        zones.append(
            f"the {count} section panels, {ARRANGEMENTS[arrangement]}, each "
            f"carrying its heading across the top and its body lines listed "
            f"left-aligned beneath it; panels vary in height ({widest} lines at "
            f"most) — align their tops, let the bottoms differ, and never pad a "
            f"short panel with invented lines"
        )

    if brief.get("diagram"):
        position = brief.get("diagram_position")
        if not position:
            position = "center" if arrangement in _CENTRED else "below"
        if position not in DIAGRAM_POSITIONS:
            raise ValueError(
                f"unknown diagram_position {position!r}; choose one of "
                f"{', '.join(sorted(DIAGRAM_POSITIONS))}"
            )
        zones.append(
            f"a drawing, {DIAGRAM_POSITIONS[position]}, showing: "
            f"{brief['diagram']} — draw this as artwork and letter only the "
            f"labels it names"
        )

    if brief.get("footer"):
        zones.append("the footer line, on a rule beneath everything else")

    return "\n".join(f"({i}) {zone}." for i, zone in enumerate(zones, 1))
