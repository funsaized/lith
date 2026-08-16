"""Explicitly authorized, low-count canaries against real provider APIs."""

import os
import pathlib

import pytest

from lith import load_recipe, render_prompt
from lith.call import ImageRequest, generate
from lith.call.creds import resolve_credential
from lith.imagebytes import image_size, looks_like_image


LIVE_RECIPE = pathlib.Path(__file__).resolve().parents[1] / "recipes" / "live_test_recipe.json"
LIVE_SWITCH = "LITH_RUN_LIVE_PROVIDER_CANARIES"

pytestmark = [
    pytest.mark.live_provider,
    pytest.mark.skipif(
        os.environ.get(LIVE_SWITCH) != "1",
        reason=f"set {LIVE_SWITCH}=1 to authorize real provider calls and spend",
    ),
]


def _assert_live_result(result, requested_aspect: str):
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.data
    assert looks_like_image(candidate.data)
    dimensions = candidate.dimensions or image_size(candidate.data)
    assert dimensions is not None
    width, height = dimensions
    requested_width, requested_height = map(float, requested_aspect.split(":"))
    assert abs(width / height - requested_width / requested_height) <= 0.02 * (
        requested_width / requested_height
    )
    assert isinstance(result.raw, dict) and result.raw
    assert isinstance(result.unsupported, dict)


def _rendered_request(model: str, **kwargs) -> ImageRequest:
    recipe = load_recipe(LIVE_RECIPE)
    rendered = render_prompt(recipe, model=model)
    return ImageRequest(
        prompt=rendered["prompt"],
        negative_prompt=rendered["negative_prompt"],
        model=model,
        aspect=rendered["aspect_ratio"],
        n=1,
        **kwargs,
    )


@pytest.mark.live_xai
def test_xai_live_canary_auth_schema_bytes_dimensions_and_metadata():
    request = _rendered_request("grok-imagine-image-2.0", resolution="1k")
    credential = resolve_credential("xai", recipe_path=LIVE_RECIPE)
    result = generate(request, credential=credential)
    _assert_live_result(result, request.aspect)
    assert result.model_reported == request.model


@pytest.mark.live_openai
def test_openai_live_canary_auth_schema_bytes_dimensions_and_metadata():
    request = _rendered_request("gpt-image-1-mini", quality="low")
    credential = resolve_credential("openai", recipe_path=LIVE_RECIPE)
    result = generate(request, credential=credential)
    _assert_live_result(result, request.aspect)
    assert result.model_reported == request.model


@pytest.mark.live_minimax
def test_minimax_live_canary_uses_compact_prompt_under_provider_cap():
    request = ImageRequest(
        prompt=(
            "Square vintage produce-label poster. Render exactly: DILL PICKLES. "
            "One glass jar, crisp cucumber spears, fresh dill, garlic, clean white background."
        ),
        model="image-01",
        aspect="1:1",
        n=1,
        seed=1047,
    )
    assert len(request.prompt) < 1500
    credential = resolve_credential("minimax", recipe_path=LIVE_RECIPE)
    result = generate(request, credential=credential)
    _assert_live_result(result, request.aspect)
    assert result.raw.get("metadata") is not None
