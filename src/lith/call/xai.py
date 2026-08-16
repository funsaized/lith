"""xAI image-generation adapter."""

from __future__ import annotations

import base64
import binascii
from typing import Any

from lith.imagebytes import _image_ext, _image_size

from . import CallResult, Candidate, ImageRequest
from .creds import Credential, resolve_credential
from .http import AuthError, InvalidRequest, ProviderError, post_json


GENERATIONS_URL = "https://api.x.ai/v1/images/generations"
GENERATION_TIMEOUT = 180.0
_MIME_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def build_request(request: ImageRequest) -> dict[str, Any]:
    """Translate a uniform request into xAI's exact JSON request body."""
    if isinstance(request.n, bool) or not isinstance(request.n, int) or not 1 <= request.n <= 10:
        raise InvalidRequest(f"xAI n must be an integer from 1 through 10; got {request.n!r}")
    if request.resolution is not None and request.resolution not in {"1k", "2k"}:
        raise InvalidRequest(
            f"xAI resolution must be '1k' or '2k'; got {request.resolution!r}"
        )
    if request.aspect == "auto":
        raise InvalidRequest(
            "lith-call requires a concrete aspect ratio and never sends 'auto'"
        )

    body: dict[str, Any] = {
        "model": request.model,
        "prompt": request.prompt,
        "n": request.n,
        "aspect_ratio": request.aspect,
        "response_format": "b64_json",
    }
    if request.resolution is not None:
        body["resolution"] = request.resolution
    return body


def unsupported_fields(request: ImageRequest) -> dict[str, str]:
    """Report every supplied uniform field that xAI cannot accept."""
    reasons = {
        "negative_prompt": "xAI image generation does not accept negative_prompt",
        "seed": "xAI image generation does not accept seed",
        "quality": "xAI image generation does not accept quality",
        "background": "xAI image generation does not accept background",
    }
    return {
        field: reason
        for field, reason in reasons.items()
        if getattr(request, field) is not None
    }


def _mime_type(item: dict[str, Any], data: bytes) -> str:
    reported = item.get("mime_type")
    if isinstance(reported, str) and reported:
        return reported
    return _MIME_BY_EXTENSION.get(_image_ext(data), "application/octet-stream")


def _candidates(payload: dict[str, Any]) -> list[Candidate]:
    items = payload.get("data")
    if not isinstance(items, list):
        raise ProviderError("xAI response has no data list", payload=payload)

    candidates: list[Candidate] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ProviderError(
                f"xAI candidate {index} is not an object", payload=payload
            )
        encoded = item.get("b64_json")
        if not isinstance(encoded, str):
            raise ProviderError(
                f"xAI candidate {index} has no b64_json", payload=payload
            )
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ProviderError(
                f"xAI candidate {index} has invalid b64_json", payload=payload
            ) from exc
        candidates.append(
            Candidate(
                index=index,
                data=data,
                mime=_mime_type(item, data),
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


def _cost(payload: dict[str, Any]) -> str | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    ticks = usage.get("cost_in_usd_ticks")
    return None if ticks is None else str(ticks)


def generate(
    request: ImageRequest, *, credential: Credential | None = None
) -> CallResult:
    """Generate xAI candidates without altering the authored prompt."""
    body = build_request(request)
    resolved = credential or resolve_credential("xai")
    if resolved.provider != "xai":
        raise ValueError(
            f"xAI adapter requires an xai credential; got {resolved.provider!r}"
        )

    try:
        payload = post_json(
            GENERATIONS_URL,
            body,
            headers={"Authorization": f"Bearer {resolved.secret}"},
            timeout=GENERATION_TIMEOUT,
        )
    except AuthError as exc:
        if resolved.is_oauth:
            raise AuthError(
                "token expired — let Hermes refresh it",
                status_code=exc.status_code,
                payload=exc.payload,
            ) from exc
        raise

    return CallResult(
        candidates=_candidates(payload),
        # The live API omits a top-level model even when it accepts an explicit
        # model id. Preserve a reported value when present; otherwise the
        # successful explicit request is the only non-speculative served id.
        model_reported=_reported_string(payload.get("model")) or request.model,
        aspect_reported=_reported_string(payload.get("aspect_ratio")),
        revised_prompt=_revised_prompt(payload),
        unsupported=unsupported_fields(request),
        cost=_cost(payload),
        raw=payload,
    )
