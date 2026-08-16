from typing import Any

from .aspect import ratio, resolve_aspect
from .layout import format_layout
from .recipe import Recipe
from .styles import get_family, load_styles


def _palette_value(field: Any, default: str) -> str:
    """Resolve a palette field to a string suitable for prompt insertion.

    List values are joined with ' | ' — this matches the original
    plate.py behavior for A_sticker's multi-accent palette. Picking
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
    if brief.get("footer"):
        parts.append(f"FOOTER: {brief['footer']}")
    return "\n".join(parts)




def copy_note(spec: str, prompt: str) -> str | None:
    """Warn when the copy block is too thin to hold the model's attention.

    The template is a fixed cost — palette, mood, layout preamble — and the
    spec block is the only part that varies. When the spec is a single title
    line the model has almost nothing to letter and starts lettering the
    instructions instead: real output has printed palette hex codes and mood
    lines as if they were headings. Rendering still succeeds, because a
    title-only poster is a legitimate thing to ask for.
    """
    instructions = len(prompt) - len(spec)
    if len(spec) * 20 >= instructions:
        return None
    return (
        f"copy block is {len(spec)} chars against {instructions} chars of "
        "instructions; the model may letter template wording instead. Add "
        "sections, or expect a title-only poster"
    )


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

    aspect, aspect_note = resolve_aspect(brief, style, model)
    spec = format_spec(brief)
    width_over_height = ratio(aspect)
    landscape = bool(width_over_height and width_over_height > 1.2)

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
        spec=spec,
        layout=format_layout(brief, landscape=landscape),
    )
    return {
        "prompt": prompt,
        "negative_prompt": str(style.get("negative_prompt", "")),
        "aspect_ratio": str(aspect),
        "style": str(style["name"]),
        "aspect_note": aspect_note,
        "copy_note": copy_note(spec, prompt),
    }
