"""OpenAI image-generation adapter."""

from __future__ import annotations

import base64
import binascii
from typing import Any

from lith.aspect import pixel_size
from lith.imagebytes import _image_ext, _image_size

from . import CallResult, Candidate, ImageRequest
from .capability import MODEL_PROVIDERS
from .creds import Credential, resolve_credential
from .http import InvalidRequest, ProviderError, post_json


GENERATIONS_URL = "https://api.openai.com/v1/images/generations"
GENERATION_TIMEOUT = 180.0
_OUTPUT_FORMATS = frozenset({"png", "jpeg", "webp"})
_QUALITY_VALUES = frozenset({"high", "medium", "low", "auto"})
_BACKGROUND_VALUES = frozenset({"transparent", "opaque", "auto"})
_MODERATION_VALUES = frozenset({"low", "auto"})
_MIME_BY_FORMAT = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}
_MIME_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
}


def _one_of(name: str, value: str, allowed: frozenset[str]) -> None:
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise InvalidRequest(f"OpenAI {name} must be one of {choices}; got {value!r}")


def build_request(
    request: ImageRequest,
    *,
    output_format: str = "png",
    output_compression: int = 100,
    moderation: str = "auto",
) -> dict[str, Any]:
    """Translate a uniform request into OpenAI's generations JSON body.

    ``output_compression=100`` and ``moderation='auto'`` are the provider's
    documented defaults. Compression is sent only for JPEG and WebP.
    """
    if MODEL_PROVIDERS.get(request.model) != "openai":
        raise InvalidRequest(
            f"OpenAI adapter does not support model {request.model!r}"
        )
    if (
        isinstance(request.n, bool)
        or not isinstance(request.n, int)
        or not 1 <= request.n <= 10
    ):
        raise InvalidRequest(
            f"OpenAI n must be an integer from 1 through 10; got {request.n!r}"
        )
    _one_of("output_format", output_format, _OUTPUT_FORMATS)
    _one_of("moderation", moderation, _MODERATION_VALUES)
    if (
        isinstance(output_compression, bool)
        or not isinstance(output_compression, int)
        or not 0 <= output_compression <= 100
    ):
        raise InvalidRequest(
            "OpenAI output_compression must be an integer from 0 through 100; "
            f"got {output_compression!r}"
        )
    if output_format == "png" and output_compression != 100:
        raise InvalidRequest(
            "OpenAI output_compression is supported only with jpeg or webp"
        )
    if request.quality is not None:
        _one_of("quality", request.quality, _QUALITY_VALUES)
    if request.background is not None:
        _one_of("background", request.background, _BACKGROUND_VALUES)

    try:
        size = pixel_size(request.model, request.aspect)
    except ValueError as exc:
        raise InvalidRequest(f"OpenAI cannot map requested aspect: {exc}") from exc

    body: dict[str, Any] = {
        "model": request.model,
        "prompt": request.prompt,
        "n": request.n,
        "size": size,
        "response_format": "b64_json",
        "output_format": output_format,
        "moderation": moderation,
    }
    if request.quality is not None:
        body["quality"] = request.quality
    if request.background is not None:
        body["background"] = request.background
    if output_format in {"jpeg", "webp"}:
        body["output_compression"] = output_compression
    return body


def unsupported_fields(request: ImageRequest) -> dict[str, str]:
    """Report every supplied uniform field OpenAI generations cannot accept."""
    reasons = {
        "resolution": "OpenAI image generation accepts size, not resolution",
        "seed": "OpenAI image generation does not accept seed",
        "negative_prompt": "OpenAI image generation does not accept negative_prompt",
    }
    return {
        field: reason
        for field, reason in reasons.items()
        if getattr(request, field) is not None
    }


def _candidates(payload: dict[str, Any], output_format: str) -> list[Candidate]:
    items = payload.get("data")
    if not isinstance(items, list):
        raise ProviderError("OpenAI response has no data list", payload=payload)

    candidates: list[Candidate] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ProviderError(
                f"OpenAI candidate {index} is not an object", payload=payload
            )
        encoded = item.get("b64_json")
        if not isinstance(encoded, str):
            raise ProviderError(
                f"OpenAI candidate {index} has no b64_json", payload=payload
            )
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ProviderError(
                f"OpenAI candidate {index} has invalid b64_json", payload=payload
            ) from exc
        extension = _image_ext(data)
        mime = _MIME_BY_EXTENSION.get(extension, _MIME_BY_FORMAT[output_format])
        candidates.append(
            Candidate(
                index=index,
                data=data,
                mime=mime,
                dimensions=_image_size(data),
            )
        )
    return candidates


def _reported_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _revised_prompt(payload: dict[str, Any]) -> str | None:
    items = payload.get("data")
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("revised_prompt"), str):
            return item["revised_prompt"]
    return None


def _headers(credential: Credential) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {credential.secret}"}
    if credential.organization_id:
        headers["OpenAI-Organization"] = credential.organization_id
    if credential.project_id:
        headers["OpenAI-Project"] = credential.project_id
    return headers


def generate(
    request: ImageRequest,
    *,
    credential: Credential | None = None,
    output_format: str = "png",
    output_compression: int = 100,
    moderation: str = "auto",
) -> CallResult:
    """Generate OpenAI candidates without altering the authored prompt."""
    body = build_request(
        request,
        output_format=output_format,
        output_compression=output_compression,
        moderation=moderation,
    )
    resolved = credential or resolve_credential("openai")
    if resolved.provider != "openai":
        raise ValueError(
            f"OpenAI adapter requires an openai credential; got {resolved.provider!r}"
        )
    payload = post_json(
        GENERATIONS_URL,
        body,
        headers=_headers(resolved),
        timeout=GENERATION_TIMEOUT,
    )
    return CallResult(
        candidates=_candidates(payload, output_format),
        model_reported=_reported_string(payload.get("model")) or request.model,
        aspect_reported=_reported_string(payload.get("aspect_ratio")),
        revised_prompt=_revised_prompt(payload),
        unsupported=unsupported_fields(request),
        cost=None,
        raw=payload,
    )
