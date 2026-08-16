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

from dataclasses import dataclass
from math import gcd
from typing import Any

@dataclass(frozen=True)
class PixelSizeRange:
    """Constraints on a model that accepts arbitrary concrete pixel sizes."""

    edge_multiple: int
    min_aspect: float
    max_aspect: float
    min_pixels: int
    max_pixels: int
    max_edge: int
    allows_auto: bool = False


@dataclass(frozen=True)
class ModelCapability:
    """The image limits for one model.

    Exactly one aspect variant is populated: a ratio enum, a fixed list of
    pixel sizes, or a constrained pixel-size range.  Request-count and prompt
    limits belong to the same record because they vary by model too.
    """

    n_max: int
    prompt_max_chars: int | None = None
    ratio_enum: frozenset[str] | None = None
    pixel_sizes: tuple[str, ...] | None = None
    pixel_range: PixelSizeRange | None = None

    def __post_init__(self) -> None:
        variants = (self.ratio_enum, self.pixel_sizes, self.pixel_range)
        if sum(value is not None for value in variants) != 1:
            raise ValueError("a model capability must define exactly one aspect variant")
        if self.n_max < 1:
            raise ValueError("n_max must be at least 1")
        if self.prompt_max_chars is not None and self.prompt_max_chars < 1:
            raise ValueError("prompt_max_chars must be at least 1")

    def __contains__(self, aspect: object) -> bool:
        """Return whether a concrete ratio is admitted by this capability.

        Resolution still deliberately uses the pre-existing finite samples for
        a constrained range.  Range-aware clamping is a separate change.
        """
        if not isinstance(aspect, str):
            return False
        if self.ratio_enum is not None:
            return aspect in self.ratio_enum
        if self.pixel_sizes is not None:
            return aspect in _pixel_size_ratios(self.pixel_sizes)
        value = ratio(aspect)
        assert self.pixel_range is not None
        return (
            value is not None
            and self.pixel_range.min_aspect <= value <= self.pixel_range.max_aspect
        )


# A model absent from the table is treated as unconstrained.  The values below
# intentionally retain their pre-P0-2 model coverage; correcting and expanding
# the entries is the next task.
_GROK_1X = frozenset(
    {"1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2"}
)
_GPT_IMAGE_2_RESOLVER_SAMPLES = frozenset(
    {
        "1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "2:1", "1:2",
        "5:4", "4:5", "3:1", "1:3", "21:9", "9:21",
    }
)

MODEL_ASPECTS: dict[str, ModelCapability] = {
    # Current generation.
    "grok-imagine-image-2.0": ModelCapability(
        ratio_enum=_GROK_1X | {"20:9", "9:20"}, n_max=10
    ),
    "gpt-image-2": ModelCapability(
        pixel_range=PixelSizeRange(
            edge_multiple=16,
            min_aspect=1 / 3,
            max_aspect=3,
            min_pixels=655_360,
            max_pixels=8_294_400,
            max_edge=3840,
            allows_auto=True,
        ),
        n_max=10,
    ),
    # Previous generation, still callable.
    "grok-imagine-image-quality": ModelCapability(ratio_enum=_GROK_1X, n_max=10),
    "grok-imagine-image": ModelCapability(ratio_enum=_GROK_1X, n_max=10),
    "gpt-image-1": ModelCapability(
        pixel_sizes=("1024x1024", "1536x1024", "1024x1536", "auto"), n_max=10
    ),
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


def supported_by(model: str | None) -> ModelCapability | None:
    """The capability for ``model``, or None if it is unconstrained."""
    return MODEL_ASPECTS.get(model) if model else None


def _pixel_size_ratios(pixel_sizes: tuple[str, ...]) -> frozenset[str]:
    """Reduce concrete ``WIDTHxHEIGHT`` values to their ratio spellings."""
    ratios: set[str] = set()
    for size in pixel_sizes:
        if "x" not in size:
            continue
        width_text, height_text = size.split("x", 1)
        try:
            width, height = int(width_text), int(height_text)
        except ValueError:
            continue
        divisor = gcd(width, height)
        ratios.add(f"{width // divisor}:{height // divisor}")
    return frozenset(ratios)


def _resolver_ratios(model: str, capability: ModelCapability) -> frozenset[str]:
    """Finite choices used by the existing resolver.

    A later task makes clamping range-aware.  Until then gpt-image-2 keeps the
    same samples the old table exposed, while its real constraints are already
    represented by ``pixel_range``.
    """
    if capability.ratio_enum is not None:
        return capability.ratio_enum - {"auto"}
    if capability.pixel_sizes is not None:
        return _pixel_size_ratios(capability.pixel_sizes)
    if model == "gpt-image-2":
        return _GPT_IMAGE_2_RESOLVER_SAMPLES
    return frozenset()


def unsupported_aspect(model: str, aspect: str) -> str | None:
    """Name the supported set when a model cannot produce ``aspect``."""
    capability = supported_by(model)
    if capability is None:
        return None
    supported = _resolver_ratios(model, capability)
    if aspect in supported:
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
    capability = supported_by(model)
    if capability is None:
        return aspect
    supported = _resolver_ratios(model or "", capability)
    if aspect in supported:
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
