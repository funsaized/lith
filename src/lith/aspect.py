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
        """Return whether a concrete ratio is admitted by this capability."""
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


# A model absent from the table is treated as unconstrained.
_XAI_RATIOS = frozenset(
    {
        "1:1", "3:4", "4:3", "9:16", "16:9", "2:3", "3:2",
        "9:19.5", "19.5:9", "9:20", "20:9", "1:2", "2:1", "auto",
    }
)
_MINIMAX_RATIOS = frozenset(
    {"1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"}
)
_XAI_1X_RATIOS = frozenset(
    {"1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2"}
)
_OPENAI_1X_SIZES = ("1024x1024", "1536x1024", "1024x1536", "auto")
_GPT_IMAGE_2_RANGE = PixelSizeRange(
    edge_multiple=16,
    min_aspect=1 / 3,
    max_aspect=3,
    min_pixels=655_360,
    max_pixels=8_294_400,
    max_edge=3840,
    allows_auto=True,
)
MODEL_ASPECTS: dict[str, ModelCapability] = {
    "grok-imagine-image-2.0": ModelCapability(ratio_enum=_XAI_RATIOS, n_max=10),
    "grok-imagine-image-quality": ModelCapability(
        ratio_enum=_XAI_1X_RATIOS, n_max=10
    ),
    "grok-imagine-image": ModelCapability(ratio_enum=_XAI_1X_RATIOS, n_max=10),
    "gpt-image-2": ModelCapability(pixel_range=_GPT_IMAGE_2_RANGE, n_max=10),
    "gpt-image-2-2026-04-21": ModelCapability(
        pixel_range=_GPT_IMAGE_2_RANGE, n_max=10
    ),
    "gpt-image-1.5": ModelCapability(pixel_sizes=_OPENAI_1X_SIZES, n_max=10),
    "gpt-image-1": ModelCapability(pixel_sizes=_OPENAI_1X_SIZES, n_max=10),
    "gpt-image-1-mini": ModelCapability(pixel_sizes=_OPENAI_1X_SIZES, n_max=10),
    "image-01": ModelCapability(
        ratio_enum=_MINIMAX_RATIOS, n_max=9, prompt_max_chars=1500
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


def _resolver_ratios(capability: ModelCapability) -> frozenset[str]:
    """Finite choices used when an enum or range boundary needs clamping."""
    if capability.ratio_enum is not None:
        return capability.ratio_enum - {"auto"}
    if capability.pixel_sizes is not None:
        return _pixel_size_ratios(capability.pixel_sizes)
    if capability.pixel_range is not None:
        return frozenset({"1:3", "3:1"})
    return frozenset()


def unsupported_aspect(model: str, aspect: str) -> str | None:
    """Name the supported set when a model cannot produce ``aspect``."""
    capability = supported_by(model)
    if capability is None:
        return None
    if capability.pixel_range is not None and aspect in capability:
        return None
    supported = _resolver_ratios(capability)
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
    if capability.pixel_range is not None and aspect in capability:
        return aspect
    supported = _resolver_ratios(capability)
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


def pixel_size(model: str, aspect: str) -> str:
    """Translate a ratio into a provider pixel size for an OpenAI model.

    Fixed-size models use their documented lookup after the same visible
    clamping as :func:`resolve_aspect`.  A constrained-range model searches
    concrete edge multiples and chooses the smallest-area size among the most
    accurate ratios.  The search is pure and deterministic.
    """
    capability = supported_by(model)
    if capability is None:
        raise ValueError(f"unknown model has no pixel-size capability: {model}")

    if capability.pixel_sizes is not None:
        resolved = nearest_supported(model, aspect)
        for size in capability.pixel_sizes:
            if "x" not in size:
                continue
            if resolved in _pixel_size_ratios((size,)):
                return size
        raise ValueError(f"{model} cannot map aspect {aspect} to a pixel size")

    limits = capability.pixel_range
    if limits is None:
        raise ValueError(f"{model} accepts ratios rather than pixel sizes")

    wanted = ratio(aspect)
    if wanted is None:
        raise ValueError(f"invalid aspect ratio: {aspect!r}")
    if not limits.min_aspect <= wanted <= limits.max_aspect:
        raise ValueError(
            f"{model} cannot reach aspect {aspect}; ratio {wanted:g} is outside "
            f"[{limits.min_aspect:g}, {limits.max_aspect:g}]"
        )

    step = limits.edge_multiple
    best: tuple[float, int, int, int] | None = None
    for height in range(step, limits.max_edge + 1, step):
        for width in range(step, limits.max_edge + 1, step):
            pixels = width * height
            if not limits.min_pixels <= pixels <= limits.max_pixels:
                continue
            error = abs((width / height) - wanted) / wanted
            candidate = (error, pixels, width, height)
            if best is None or candidate < best:
                best = candidate

    if best is None:
        raise ValueError(
            f"{model} cannot reach aspect {aspect} within its pixel constraints"
        )
    _, _, width, height = best
    return f"{width}x{height}"


def request_limit_notes(model: str, n: int, prompt: str) -> list[str]:
    """Describe model request limits exceeded by a rendered envelope."""
    capability = supported_by(model)
    if capability is None:
        return []
    notes = []
    if n > capability.n_max:
        notes.append(
            f"{model} requested n={n}; maximum is {capability.n_max}"
        )
    if (
        capability.prompt_max_chars is not None
        and len(prompt) > capability.prompt_max_chars
    ):
        notes.append(
            f"{model} prompt is {len(prompt)} characters; maximum is "
            f"{capability.prompt_max_chars} (backlog §3.1)"
        )
    return notes


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
