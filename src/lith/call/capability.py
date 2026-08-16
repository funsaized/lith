"""Provider routing for every model in lith's capability table."""

from __future__ import annotations


MODEL_PROVIDERS: dict[str, str] = {
    "grok-imagine-image-2.0": "xai",
    "grok-imagine-image-quality": "xai",
    "grok-imagine-image": "xai",
    "gpt-image-2": "openai",
    "gpt-image-2-2026-04-21": "openai",
    "gpt-image-1.5": "openai",
    "gpt-image-1": "openai",
    "gpt-image-1-mini": "openai",
    "image-01": "minimax",
}


def provider_for_model(model: str) -> str:
    """Return the provider adapter name for ``model``."""
    try:
        return MODEL_PROVIDERS[model]
    except KeyError as exc:
        supported = ", ".join(sorted(MODEL_PROVIDERS))
        raise ValueError(
            f"unknown image model {model!r}; supported models: {supported}"
        ) from exc
