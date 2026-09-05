"""MiniMax text-to-image adapter with lith's prompt-length precondition."""

from __future__ import annotations

import base64
import binascii
from fractions import Fraction
from math import ceil, gcd, lcm
from typing import Any

from lith.aspect import ratio
from lith.imagebytes import image_ext, image_size

from . import CallResult, Candidate, ImageRequest
from .creds import Credential, resolve_credential
from .http import InvalidRequest, ProviderError, post_json


GENERATIONS_URL = "https://api.minimax.io/v1/image_generation"
MODEL = "image-01"
PROMPT_MAX_CHARS = 1500
SUPPORTED_ASPECTS = frozenset(
    {"1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"}
)
_MIME_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class PromptTooLong(InvalidRequest):
    """A prompt that MiniMax cannot accept without changing lith's design."""


def _validate_prompt(prompt: str) -> None:
    length = len(prompt)
    if length > PROMPT_MAX_CHARS:
        raise PromptTooLong(
            f"MiniMax prompt length is {length} characters; cap is "
            f"{PROMPT_MAX_CHARS}. Use an explicitly authored shorter brief or "
            "the supported family B compact prompt_mode; no copy was changed"
        )


def _pixel_dimensions(aspect: str) -> tuple[int, int]:
    requested = ratio(aspect)
    if requested is None or requested <= 0:
        raise InvalidRequest(f"MiniMax requires a positive W:H aspect; got {aspect!r}")

    width_text, height_text = aspect.split(":", 1)
    exact = Fraction(width_text) / Fraction(height_text)
    factor = lcm(8 // gcd(exact.numerator, 8), 8 // gcd(exact.denominator, 8))
    width_unit = exact.numerator * factor
    height_unit = exact.denominator * factor
    minimum_scale = max(ceil(512 / width_unit), ceil(512 / height_unit))
    maximum_scale = min(2048 // width_unit, 2048 // height_unit)

    if minimum_scale <= maximum_scale:
        width = width_unit * maximum_scale
        height = height_unit * maximum_scale
    elif requested >= 1:
        width = 2048
        height = max(512, min(2048, round(width / requested / 8) * 8))
    else:
        height = 2048
        width = max(512, min(2048, round(height * requested / 8) * 8))

    error = abs(width / height - requested) / requested
    if error > 0.01:
        raise InvalidRequest(
            f"MiniMax cannot represent aspect {aspect!r} within 1% using "
            "width/height from 512 through 2048 divisible by 8"
        )
    return width, height


def build_request(request: ImageRequest) -> dict[str, Any]:
    """Translate a compact uniform request into MiniMax's t2i JSON body."""
    _validate_prompt(request.prompt)
    if request.model != MODEL:
        raise InvalidRequest(
            f"MiniMax text-to-image supports only {MODEL!r}; got {request.model!r}"
        )
    if isinstance(request.n, bool) or not isinstance(request.n, int) or not 1 <= request.n <= 9:
        raise InvalidRequest(
            f"MiniMax n must be an integer from 1 through 9; got {request.n!r}"
        )
    if request.seed is not None and (
        isinstance(request.seed, bool) or not isinstance(request.seed, int)
    ):
        raise InvalidRequest(f"MiniMax seed must be an integer; got {request.seed!r}")

    body: dict[str, Any] = {
        "model": MODEL,
        "prompt": request.prompt,
        "n": request.n,
        "prompt_optimizer": False,
        "response_format": "base64",
    }
    if request.seed is not None:
        body["seed"] = request.seed
    if request.aspect in SUPPORTED_ASPECTS:
        body["aspect_ratio"] = request.aspect
    else:
        width, height = _pixel_dimensions(request.aspect)
        body["width"] = width
        body["height"] = height
    return body


def unsupported_fields(request: ImageRequest) -> dict[str, str]:
    """Report uniform fields that MiniMax t2i cannot accept."""
    reasons = {
        "negative_prompt": "MiniMax image generation does not accept negative_prompt",
        "resolution": "MiniMax does not accept lith's 1k/2k resolution field",
        "quality": "MiniMax image generation does not accept quality",
        "background": "MiniMax image generation does not accept background",
    }
    return {
        field: reason
        for field, reason in reasons.items()
        if getattr(request, field) is not None
    }


def _mime_type(data: bytes) -> str:
    return _MIME_BY_EXTENSION.get(image_ext(data), "application/octet-stream")


def _candidates(payload: dict[str, Any]) -> list[Candidate]:
    data_object = payload.get("data")
    if not isinstance(data_object, dict):
        raise ProviderError("MiniMax response has no data object", payload=payload)
    images = data_object.get("image_base64")
    if not isinstance(images, list):
        raise ProviderError(
            "MiniMax response has no image_base64 list", payload=payload
        )

    candidates: list[Candidate] = []
    for index, encoded in enumerate(images):
        if not isinstance(encoded, str):
            raise ProviderError(
                f"MiniMax candidate {index} is not base64 text", payload=payload
            )
        try:
            image = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ProviderError(
                f"MiniMax candidate {index} has invalid base64", payload=payload
            ) from exc
        candidates.append(
            Candidate(
                index=index,
                data=image,
                mime=_mime_type(image),
                dimensions=image_size(image),
            )
        )
    return candidates


def _reported_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def generate(
    request: ImageRequest, *, credential: Credential | None = None
) -> CallResult:
    """Generate a batch from MiniMax after enforcing its 1500-char cap."""
    body = build_request(request)
    resolved = credential or resolve_credential("minimax")
    if resolved.provider != "minimax":
        raise ValueError(
            f"MiniMax adapter requires a minimax credential; got {resolved.provider!r}"
        )
    payload = post_json(
        GENERATIONS_URL,
        body,
        headers={"Authorization": f"Bearer {resolved.secret}"},
    )
    return CallResult(
        candidates=_candidates(payload),
        model_reported=_reported_string(payload.get("model")),
        aspect_reported=_reported_string(payload.get("aspect_ratio")),
        revised_prompt=None,
        unsupported=unsupported_fields(request),
        cost=None,
        raw=payload,
    )
