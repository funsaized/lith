import base64
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lith import load_recipe, render_prompt
from lith.call import ImageRequest
from lith.call.creds import Credential
from lith.call.http import (
    AuthError,
    ContentRejected,
    InvalidRequest,
    ProviderError,
    RateLimited,
)
from lith.call.minimax import (
    GENERATIONS_URL,
    PROMPT_MAX_CHARS,
    PromptTooLong,
    build_request,
    generate,
)


REPO = Path(__file__).resolve().parents[1]


class Response:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()
        self.status = 200
        self.reason = "OK"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body


def credential(provider="minimax"):
    return Credential(
        provider=provider,
        secret="fixture-secret",
        tier=1,
        source="fixture",
        auth_type="api_key",
    )


def png(width, height):
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00" * 8
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
    )


def success(*images):
    return {
        "id": "fixture-id",
        "data": {"image_base64": [base64.b64encode(image).decode() for image in images]},
        "metadata": {"success_count": len(images), "failed_count": 0},
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }


def test_supported_aspect_builds_exact_batched_body_and_parses_candidates():
    first = png(1024, 1024)
    second = png(1024, 1024)
    payload = success(first, second)
    request = ImageRequest(
        prompt="compact prompt",
        model="image-01",
        aspect="1:1",
        n=2,
        seed=42,
    )
    with patch("lith.call.minimax.post_json", return_value=payload) as post:
        result = generate(request, credential=credential())

    post.assert_called_once_with(
        GENERATIONS_URL,
        {
            "model": "image-01",
            "prompt": "compact prompt",
            "n": 2,
            "prompt_optimizer": False,
            "response_format": "base64",
            "seed": 42,
            "aspect_ratio": "1:1",
        },
        headers={"Authorization": "Bearer fixture-secret"},
    )
    assert [candidate.index for candidate in result.candidates] == [0, 1]
    assert [candidate.data for candidate in result.candidates] == [first, second]
    assert [candidate.mime for candidate in result.candidates] == [
        "image/png",
        "image/png",
    ]
    assert [candidate.dimensions for candidate in result.candidates] == [
        (1024, 1024),
        (1024, 1024),
    ]
    assert result.raw is payload
    assert result.raw["metadata"] == {"success_count": 2, "failed_count": 0}
    assert result.model_reported is None
    assert result.aspect_reported is None
    assert result.revised_prompt is None
    assert result.cost is None


def test_unlisted_aspect_uses_valid_explicit_dimensions_within_one_percent():
    request = ImageRequest(
        prompt="compact prompt", model="image-01", aspect="20:9"
    )
    body = build_request(request)
    assert "aspect_ratio" not in body
    width, height = body["width"], body["height"]
    assert 512 <= width <= 2048
    assert 512 <= height <= 2048
    assert width % 8 == 0
    assert height % 8 == 0
    assert abs(width / height - 20 / 9) / (20 / 9) <= 0.01


def test_unsupported_fields_are_reported_without_touching_prompt():
    prompt = "POSITIVE ONLY; preserve exactly"
    request = ImageRequest(
        prompt=prompt,
        model="image-01",
        aspect="16:9",
        negative_prompt="watermarks",
        resolution="2k",
        quality="high",
        background="transparent",
    )
    with patch("lith.call.minimax.post_json", return_value=success(png(16, 9))) as post:
        result = generate(request, credential=credential())
    sent = post.call_args.args[1]
    assert sent["prompt"] == prompt
    assert "watermarks" not in sent["prompt"]
    assert "negative_prompt" not in sent
    assert "resolution" not in sent
    assert "quality" not in sent
    assert "background" not in sent
    assert result.unsupported == {
        "negative_prompt": "MiniMax image generation does not accept negative_prompt",
        "resolution": "MiniMax does not accept lith's 1k/2k resolution field",
        "quality": "MiniMax image generation does not accept quality",
        "background": "MiniMax image generation does not accept background",
    }


def test_standard_testbed_recipe_exceeds_cap_before_auth_or_network():
    recipe_path = REPO / "recipes" / "integration" / "06-grid-3x2-F.json"
    recipe = load_recipe(recipe_path)
    assert recipe.model == "image-01"
    rendered = render_prompt(recipe)
    measured = len(rendered["prompt"])
    assert measured > PROMPT_MAX_CHARS
    request = ImageRequest(
        prompt=rendered["prompt"],
        model=recipe.model,
        aspect=rendered["aspect_ratio"],
        n=recipe.n,
        negative_prompt=rendered["negative_prompt"],
    )
    with (
        patch("lith.call.minimax.resolve_credential") as resolve,
        patch("lith.call.minimax.post_json") as post,
    ):
        with pytest.raises(PromptTooLong) as raised:
            generate(request)
    message = str(raised.value)
    assert str(measured) in message
    assert str(PROMPT_MAX_CHARS) in message
    assert "compact prompt_mode" in message
    resolve.assert_not_called()
    post.assert_not_called()


@pytest.mark.parametrize("n", [0, 10, True, 1.5])
def test_n_must_be_an_integer_from_one_through_nine(n):
    request = ImageRequest(prompt="compact", model="image-01", aspect="1:1", n=n)
    with pytest.raises(InvalidRequest, match="n must be an integer from 1 through 9"):
        build_request(request)


def test_invalid_seed_model_and_unreachable_ratio_are_rejected():
    with pytest.raises(InvalidRequest, match="seed must be an integer"):
        build_request(
            ImageRequest(
                prompt="compact", model="image-01", aspect="1:1", seed=True
            )
        )
    with pytest.raises(InvalidRequest, match="supports only 'image-01'"):
        build_request(
            ImageRequest(prompt="compact", model="image-01-live", aspect="1:1")
        )
    with pytest.raises(InvalidRequest, match="cannot represent aspect"):
        build_request(
            ImageRequest(prompt="compact", model="image-01", aspect="20:1")
        )
    with pytest.raises(InvalidRequest, match="positive W:H"):
        build_request(ImageRequest(prompt="compact", model="image-01", aspect="auto"))


def test_resolves_minimax_credential_only_when_absent_and_rejects_wrong_provider():
    request = ImageRequest(prompt="compact", model="image-01", aspect="1:1")
    resolved = credential()
    with (
        patch("lith.call.minimax.resolve_credential", return_value=resolved) as resolve,
        patch("lith.call.minimax.post_json", return_value=success(png(10, 10))),
    ):
        generate(request)
    resolve.assert_called_once_with("minimax")

    with patch("lith.call.minimax.post_json") as post:
        with pytest.raises(ValueError, match="requires a minimax credential"):
            generate(request, credential=credential(provider="xai"))
    post.assert_not_called()


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (1002, RateLimited),
        (1004, AuthError),
        (1008, ProviderError),
        (1026, ContentRejected),
        (2013, InvalidRequest),
        (2049, AuthError),
    ],
)
def test_minimax_200_body_status_maps_through_transport(code, expected):
    payload = {
        "base_resp": {"status_code": code, "status_msg": "fixture failure"},
        "data": {},
    }
    request = ImageRequest(prompt="compact", model="image-01", aspect="1:1")
    with patch("urllib.request.urlopen", return_value=Response(payload)):
        with pytest.raises(expected) as raised:
            generate(request, credential=credential())
    assert raised.value.status_code == code


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "no data object"),
        ({"data": {}}, "no image_base64 list"),
        ({"data": {"image_base64": [3]}}, "candidate 0 is not base64 text"),
        ({"data": {"image_base64": ["%%%"]}}, "candidate 0 has invalid base64"),
    ],
)
def test_invalid_candidate_shapes_are_provider_errors(payload, message):
    request = ImageRequest(prompt="compact", model="image-01", aspect="1:1")
    with patch("lith.call.minimax.post_json", return_value=payload):
        with pytest.raises(ProviderError, match=message):
            generate(request, credential=credential())
