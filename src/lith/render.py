from typing import Any

from .aspect import resolve_aspect
from .recipe import Recipe
from .styles import get_family, load_styles


def _palette_value(field: Any, default: str) -> str:
    """Resolve a palette field to a string suitable for prompt insertion.

    List values are joined with ' | ' — this matches the original
    generate.py behavior for A_sticker's multi-accent palette. Picking
    field[0] would silently change only A_sticker's prompt.
    """
    if isinstance(field, list):
        if not field:
            return default
        return " | ".join(str(x) for x in field)
    return field or default


def format_spec(brief: dict[str, Any]) -> str:
    """Serialize a poster spec into a literal copy block for the prompt.

    Every line this emits is text the model is told to render character for
    character. A brief with no ``sections`` degrades to just the title, which
    is what pre-spec recipes produce.
    """
    parts = []
    title = brief.get("title") or brief.get("headline")
    if title:
        parts.append(f"TITLE: {title}")
    if brief.get("subtitle"):
        parts.append(f"SUBTITLE: {brief['subtitle']}")
    for index, section in enumerate(brief.get("sections", []), 1):
        if "heading" not in section:
            raise ValueError(f"brief section {index} has no 'heading': {section!r}")
        block = [f"SECTION {index} HEADING: {section['heading']}"]
        block += [f"    - {line}" for line in section.get("lines", [])]
        parts.append("\n".join(block))
    if brief.get("diagram"):
        parts.append(f"DIAGRAM: {brief['diagram']}")
    if brief.get("footer"):
        parts.append(f"FOOTER: {brief['footer']}")
    return "\n".join(parts)


def format_layout(brief: dict[str, Any]) -> str:
    """Describe only the zones the spec actually has copy for.

    An unconditional four-zone skeleton contradicts the verbatim-copy rule:
    ordered to draw a section grid with no sections to put in it, the model
    invents filler. Zones track the spec so sparse and dense briefs both work.
    """
    sections = brief.get("sections", [])
    if sections:
        title_size = "12-15% of frame height"
    else:
        # No body copy to compete with, so the title carries the whole poster.
        title_size = "30-40% of frame height, dominating the composition"
    title = f"TITLE BLOCK — the title set at {title_size}"
    if brief.get("subtitle"):
        title += ", with the subtitle centered beneath it at half that size"
    zones = [title]

    if sections:
        # ponytail: fixed thresholds, tune if 7+ section posters become common.
        count = len(sections)
        grid = "a single column" if count <= 2 else "two columns"
        widest = max(len(s.get("lines", [])) for s in sections)
        zones.append(
            f"{count} SECTION PANELS laid out in {grid}, one panel per section, "
            f"each with its heading across the top and its body lines listed "
            f"left-aligned beneath it. Panels vary in height ({widest} lines at "
            f"most) — align their tops, let the bottoms differ, and never pad a "
            f"short panel with invented lines"
        )
    if brief.get("diagram"):
        zones.append("DIAGRAM PANEL — full width, holding the labeled diagram")
    if brief.get("footer"):
        zones.append("FOOTER — a rule with the footer text beneath")

    return "\n".join(f"({i}) {zone}." for i, zone in enumerate(zones, 1))


def render_prompt(
    style: dict[str, Any] | Recipe,
    brief: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, str]:
    """Substitute brief fields into the family's prompt template.

    Pass a ``Recipe`` by itself to use lith's bundled style definitions, or
    pass a style mapping and brief mapping to render custom definitions.

    Raises KeyError if the template references a slot not in the brief and
    not given a default. Intentional — silent drops are how the C_patent
    bug got into the repo.
    """
    if isinstance(style, Recipe):
        if brief is not None:
            raise TypeError("brief must be omitted when rendering a Recipe")
        brief = style.brief
        model = model or style.model
        style = get_family(load_styles(), style.style)
    elif brief is None:
        raise TypeError("brief is required when style is a mapping")

    palette = style.get("palette", {})
    prompt = style["prompt_template"].format(
        headline=brief.get("headline", "NEW"),
        icon=brief.get("icon", "gear"),
        # Brief wins over palette: a family whose palette lists several
        # backgrounds needs the recipe to pick one, or the prompt asks for a
        # "single flat background" and names three colors.
        base_color=_palette_value(
            brief.get("base_color") or palette.get("background"), "#000000"
        ),
        accent=_palette_value(brief.get("accent") or palette.get("accent"), "#00E5FF"),
        volume=brief.get("volume", "1"),
        spec=format_spec(brief),
        layout=format_layout(brief),
    )
    aspect, aspect_note = resolve_aspect(brief, style, model)
    return {
        "prompt": prompt,
        "negative_prompt": str(style.get("negative_prompt", "")),
        "aspect_ratio": str(aspect),
        "style": str(style["name"]),
        "aspect_note": aspect_note,
    }
