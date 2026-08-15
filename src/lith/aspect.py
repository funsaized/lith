"""Aspect-ratio resolution: what a brief asks for versus what a model can make.

Four inputs decide the final ratio, in descending precedence:

1. an explicit ``aspect`` on the brief — set by you, or by ``expand_brief``
   reading the topic
2. the shape of the content, for families that render a spec
3. the family's ``default_aspect``
4. what the target model can actually produce, which clamps whatever the
   first three chose

Step 4 exists because an image model does not reject a ratio it lacks — it
silently substitutes one. The layout in the prompt was composed for the frame
that was asked for, so the substitution has to happen here, visibly, rather
than inside the model.
"""

from __future__ import annotations

from typing import Any

# Ratios each model can produce. A model absent here is treated as
# unconstrained — minimax-image has no entry, so it is never clamped.
#
# gpt-image-2's wider set is not free: 5:4, 4:5, 3:1, 1:3 and 9:21 drop out at
# 2K and 4K. Lith does not request a resolution, so they are listed, but a
# caller pinning a large output should expect them to fail there.
_GROK_1X = {"1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2"}

MODEL_ASPECTS: dict[str, set[str]] = {
    # Current generation.
    "grok-imagine-image-2.0": _GROK_1X | {"20:9", "9:20"},
    "gpt-image-2": {
        "1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "2:1", "1:2",
        "5:4", "4:5", "3:1", "1:3", "21:9", "9:21",
    },
    # Previous generation, still callable.
    "grok-imagine-image-quality": _GROK_1X,
    "grok-imagine-image": _GROK_1X,
    "gpt-image-1": {"1:1", "3:2", "2:3"},
}

FALLBACK_ASPECT = "16:9"


def ratio(aspect: str) -> float | None:
    """Width divided by height, or None when ``aspect`` is not ``N:M``."""
    if not isinstance(aspect, str) or ":" not in aspect:
        return None
    try:
        num, den = (float(part) for part in aspect.split(":", 1))
    except ValueError:
        return None
    if not num or not den:
        return None
    return num / den


def supported_by(model: str | None) -> set[str] | None:
    """The ratios ``model`` can produce, or None if it is unconstrained."""
    return MODEL_ASPECTS.get(model) if model else None


def unsupported_aspect(model: str, aspect: str) -> str | None:
    """Name the supported set when a model cannot produce ``aspect``."""
    supported = supported_by(model)
    if supported is None or aspect in supported:
        return None
    return (
        f"{model} cannot produce {aspect}; it supports "
        f"{', '.join(sorted(supported))}"
    )


def nearest_supported(model: str | None, aspect: str) -> str:
    """The supported ratio closest to ``aspect``, or ``aspect`` unchanged.

    Closeness is measured on width/height, so a portrait request lands on a
    portrait ratio rather than on whichever string happens to sort first.
    """
    supported = supported_by(model)
    if supported is None or aspect in supported:
        return aspect
    want = ratio(aspect)
    if want is None:
        return aspect
    candidates = [(a, ratio(a)) for a in supported]
    usable = [(a, r) for a, r in candidates if r is not None]
    if not usable:
        return aspect
    return min(usable, key=lambda pair: abs(pair[1] - want))[0]


def content_aspect(brief: dict[str, Any], style: dict[str, Any]) -> str | None:
    """The ratio the brief's own content shape calls for, if it calls for one.

    Only families that render a spec have content to measure. Three or more
    section panels need vertical room; one or two read better square. Anything
    else defers to the family default.
    """
    if "{spec}" not in str(style.get("prompt_template", "")):
        return None
    count = len(brief.get("sections") or [])
    if count >= 3:
        return "2:3"
    if count >= 1:
        return "1:1"
    return None


def resolve_aspect(
    brief: dict[str, Any],
    style: dict[str, Any],
    model: str | None = None,
) -> tuple[str, str | None]:
    """Resolve the final aspect ratio and any note about how it was reached.

    Returns ``(aspect, note)``. ``note`` is None when nothing was substituted.
    """
    explicit = brief.get("aspect")
    chosen = (
        explicit
        or content_aspect(brief, style)
        or style.get("default_aspect")
        or FALLBACK_ASPECT
    )
    clamped = nearest_supported(model, chosen)
    if clamped == chosen:
        return chosen, None
    return clamped, (
        f"{model} cannot produce {chosen}; using nearest supported {clamped}"
    )
