"""Explicitly authorized, low-count canaries against real provider APIs."""

import os
import pathlib

import pytest

from lith import load_recipe, render_prompt
from lith.call import CallResult, Candidate, ImageRequest, generate
from lith.call.creds import resolve_credential
from lith.imagebytes import image_ext, image_size, looks_like_image


LIVE_RECIPE = pathlib.Path(__file__).resolve().parents[1] / "recipes" / "live_test_recipe.json"
LIVE_SWITCH = "LITH_RUN_LIVE_PROVIDER_CANARIES"
LIVE_OUTPUT_DIR = "LITH_LIVE_OUTPUT_DIR"

live_only = pytest.mark.skipif(
    os.environ.get(LIVE_SWITCH) != "1",
    reason=f"set {LIVE_SWITCH}=1 to authorize real provider calls and spend",
)


def _save_live_candidates(result, *, provider: str, model: str) -> list[pathlib.Path]:
    configured = os.environ.get(LIVE_OUTPUT_DIR, "").strip()
    if not configured:
        return []
    output_dir = pathlib.Path(configured).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for candidate in result.candidates:
        extension = image_ext(candidate.data)
        assert extension is not None
        path = output_dir / f"{provider}_{model}_canary-c{candidate.index}{extension}"
        path.write_bytes(candidate.data)
        paths.append(path)
        print(f"saved live canary: {path}", flush=True)
    return paths


def _assert_live_result(result, requested_aspect: str, *, provider: str, model: str):
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
    _save_live_candidates(result, provider=provider, model=model)


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
@pytest.mark.live_provider
@live_only
def test_xai_live_canary_auth_schema_bytes_dimensions_and_metadata():
    request = _rendered_request("grok-imagine-image-2.0", resolution="1k")
    credential = resolve_credential("xai", recipe_path=LIVE_RECIPE)
    result = generate(request, credential=credential)
    _assert_live_result(result, request.aspect, provider="xai", model=request.model)
    assert result.model_reported == request.model


@pytest.mark.live_openai
@pytest.mark.live_provider
@live_only
def test_openai_live_canary_auth_schema_bytes_dimensions_and_metadata():
    request = _rendered_request("gpt-image-1-mini", quality="low")
    credential = resolve_credential("openai", recipe_path=LIVE_RECIPE)
    result = generate(request, credential=credential)
    _assert_live_result(result, request.aspect, provider="openai", model=request.model)
    assert result.model_reported == request.model


@pytest.mark.live_minimax
@pytest.mark.live_provider
@live_only
def test_minimax_live_canary_uses_compact_prompt_under_provider_cap():
    recipe = load_recipe(LIVE_RECIPE.parent / "minimax" / "sparse.json")
    rendered = render_prompt(recipe)
    request = ImageRequest(
        prompt=rendered["prompt"],
        negative_prompt=rendered["negative_prompt"],
        model=recipe.model,
        aspect=rendered["aspect_ratio"],
        n=1,
        seed=1047,
    )
    assert len(request.prompt) < 1500
    credential = resolve_credential("minimax", recipe_path=LIVE_RECIPE)
    result = generate(request, credential=credential)
    _assert_live_result(result, request.aspect, provider="minimax", model=request.model)
    assert result.raw.get("metadata") is not None


def test_live_artifact_sink_is_optional_and_uses_magic_extension(tmp_path, monkeypatch, capsys):
    result = CallResult(
        candidates=[Candidate(0, b"\x89PNG\r\n\x1a\nfixture", "image/png", (1, 1))],
        model_reported=None,
        aspect_reported=None,
        revised_prompt=None,
        unsupported={},
        cost=None,
        raw={},
    )
    monkeypatch.delenv(LIVE_OUTPUT_DIR, raising=False)
    assert _save_live_candidates(result, provider="minimax", model="image-01") == []
    monkeypatch.setenv(LIVE_OUTPUT_DIR, str(tmp_path / "canaries"))
    paths = _save_live_candidates(result, provider="minimax", model="image-01")
    assert paths == [tmp_path / "canaries" / "minimax_image-01_canary-c0.png"]
    assert paths[0].read_bytes() == result.candidates[0].data
    assert str(paths[0]) in capsys.readouterr().out
