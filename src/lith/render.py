from typing import Any

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


def render_prompt(
    style: dict[str, Any] | Recipe,
    brief: dict[str, Any] | None = None,
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
        style = get_family(load_styles(), style.style)
    elif brief is None:
        raise TypeError("brief is required when style is a mapping")

    palette = style.get("palette", {})
    prompt = style["prompt_template"].format(
        headline=brief.get("headline", "NEW"),
        icon=brief.get("icon", "gear"),
        base_color=_palette_value(palette.get("background"), "#000000"),
        accent=_palette_value(palette.get("accent"), "#00E5FF"),
        volume=brief.get("volume", "1"),
    )
    aspect = brief.get("aspect") or style.get("default_aspect", "16:9")
    return {
        "prompt": prompt,
        "negative_prompt": str(style.get("negative_prompt", "")),
        "aspect_ratio": str(aspect),
        "style": str(style["name"]),
    }
