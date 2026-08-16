"""Uniform provider-independent image generation request and result types."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from .capability import provider_for_model


@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    model: str
    aspect: str
    n: int = 1
    seed: int | None = None
    resolution: str | None = None
    quality: str | None = None
    background: str | None = None
    negative_prompt: str | None = None


@dataclass
class Candidate:
    index: int
    data: bytes
    mime: str
    dimensions: tuple[int, int] | None


@dataclass
class CallResult:
    candidates: list[Candidate]
    model_reported: str | None
    aspect_reported: str | None
    revised_prompt: str | None
    unsupported: dict[str, str]
    cost: str | None
    raw: dict


def generate(request: ImageRequest, *, credential=None) -> CallResult:
    """Dispatch ``request`` to its model's provider adapter.

    Provider modules are imported lazily so importing :mod:`lith.call` remains
    transport-neutral and offline-safe.
    """
    provider = provider_for_model(request.model)
    adapter = import_module(f"lith.call.{provider}")
    return adapter.generate(request, credential=credential)
