import base64
from unittest.mock import patch

import pytest

from lith.call import ImageRequest
from lith.call.creds import Credential
from lith.call.http import AuthError, InvalidRequest, ProviderError
from lith.call.xai import GENERATIONS_URL, GENERATION_TIMEOUT, build_request, generate


def credential(*, oauth=False, provider="xai"):
    return Credential(
        provider=provider,
        secret="fixture-secret",
        tier=4 if oauth else 1,
        source="fixture",
        auth_type="oauth" if oauth else "api_key",
    )


def png(width, height):
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00" * 8
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
    )


def response(*images, revised_prompt=""):
    return {
        "model": "grok-imagine-image-2.0",
        "aspect_ratio": "2:3",
        "data": [
            {
                "b64_json": base64.b64encode(image).decode(),
                "mime_type": "image/png",
                "revised_prompt": revised_prompt,
            }
            for image in images
        ],
        "usage": {"cost_in_usd_ticks": 987},
    }


def test_exact_request_body_and_parsed_call_result():
    first = png(1024, 1536)
    second = png(768, 1152)
    payload = response(first, second)
    request = ImageRequest(
        prompt="draw this byte-for-byte",
        model="grok-imagine-image-2.0",
        aspect="2:3",
        n=2,
        resolution="2k",
    )

    with patch("lith.call.xai.post_json", return_value=payload) as post:
        result = generate(request, credential=credential())

    post.assert_called_once_with(
        GENERATIONS_URL,
        {
            "model": "grok-imagine-image-2.0",
            "prompt": "draw this byte-for-byte",
            "n": 2,
            "aspect_ratio": "2:3",
            "response_format": "b64_json",
            "resolution": "2k",
        },
        headers={"Authorization": "Bearer fixture-secret"},
        timeout=GENERATION_TIMEOUT,
    )
    assert [candidate.index for candidate in result.candidates] == [0, 1]
    assert [candidate.data for candidate in result.candidates] == [first, second]
    assert [candidate.mime for candidate in result.candidates] == [
        "image/png",
        "image/png",
    ]
    assert [candidate.dimensions for candidate in result.candidates] == [
        (1024, 1536),
        (768, 1152),
    ]
    assert result.model_reported == "grok-imagine-image-2.0"
    assert result.aspect_reported == "2:3"
    assert result.revised_prompt == ""
    assert result.cost == "987"
    assert result.raw is payload
    assert result.unsupported == {}


def test_public_storage_uses_url_response_and_fetches_candidate_bytes():
    image = png(1280, 720)
    payload = {
        "data": [
            {
                "url": "https://files-cdn.x.ai/lith-p3-3.png",
                "mime_type": "image/png",
                "file_output": {
                    "file_id": "file-fixture",
                    "public_url": "https://files-cdn.x.ai/stored/lith-p3-3.png",
                },
            }
        ]
    }
    request = ImageRequest(
        prompt="store this byte-for-byte",
        model="grok-imagine-image-2.0",
        aspect="16:9",
    )
    storage = {
        "filename": "lith-p3-3.png",
        "expires_after": 2_592_000,
        "public_url": True,
    }

    with patch("lith.call.xai.post_json", return_value=payload) as post, patch(
        "lith.call.xai.fetch_image", return_value=image
    ) as fetch:
        result = generate(
            request, credential=credential(), storage_options=storage
        )

    assert post.call_args.args[1] == {
        "model": "grok-imagine-image-2.0",
        "prompt": "store this byte-for-byte",
        "n": 1,
        "aspect_ratio": "16:9",
        "response_format": "url",
        "storage_options": storage,
    }
    fetch.assert_called_once_with(
        "https://files-cdn.x.ai/stored/lith-p3-3.png"
    )
    assert result.candidates[0].data == image
    assert result.candidates[0].dimensions == (1280, 720)
    assert result.raw is payload


@pytest.mark.parametrize(
    ("storage", "message"),
    [
        ({}, "filename is required"),
        ({"filename": ""}, "filename is required"),
    ],
)
def test_required_storage_filename_is_validated_before_auth(storage, message):
    request = ImageRequest(
        prompt="draw", model="grok-imagine-image-2.0", aspect="1:1"
    )
    with patch("lith.call.xai.resolve_credential") as resolve:
        with pytest.raises(InvalidRequest, match=message):
            generate(request, storage_options=storage)
    resolve.assert_not_called()


def test_other_storage_options_are_passed_to_xai_for_validation():
    request = ImageRequest(
        prompt="draw", model="grok-imagine-image-2.0", aspect="1:1"
    )
    storage = {"filename": "x.png", "provider_option": "future-value"}
    assert build_request(request, storage_options=storage)["storage_options"] == storage


def test_unsupported_fields_are_reported_without_touching_prompt():
    prompt = "POSITIVE ONLY\nDo not mutate this exact string."
    request = ImageRequest(
        prompt=prompt,
        model="grok-imagine-image-2.0",
        aspect="1:1",
        seed=0,
        quality="high",
        background="transparent",
        negative_prompt="words, watermarks",
    )
    with patch("lith.call.xai.post_json", return_value=response(png(10, 10))) as post:
        result = generate(request, credential=credential())

    sent = post.call_args.args[1]
    assert sent == {
        "model": "grok-imagine-image-2.0",
        "prompt": prompt,
        "n": 1,
        "aspect_ratio": "1:1",
        "response_format": "b64_json",
    }
    assert sent["prompt"] == prompt
    assert "words, watermarks" not in sent["prompt"]
    assert result.unsupported == {
        "negative_prompt": "xAI image generation does not accept negative_prompt",
        "seed": "xAI image generation does not accept seed",
        "quality": "xAI image generation does not accept quality",
        "background": "xAI image generation does not accept background",
    }


@pytest.mark.parametrize("n", [0, 11, True, 1.5])
def test_n_must_be_an_integer_from_one_through_ten(n):
    request = ImageRequest(
        prompt="draw", model="grok-imagine-image-2.0", aspect="1:1", n=n
    )
    with patch("lith.call.xai.resolve_credential") as resolve, patch(
        "lith.call.xai.post_json"
    ) as post:
        with pytest.raises(InvalidRequest, match="n must be an integer from 1 through 10"):
            generate(request)
    resolve.assert_not_called()
    post.assert_not_called()


def test_resolution_is_optional_and_validated_before_auth():
    request = ImageRequest(
        prompt="draw",
        model="grok-imagine-image-2.0",
        aspect="1:1",
        resolution="4k",
    )
    with patch("lith.call.xai.resolve_credential") as resolve:
        with pytest.raises(InvalidRequest, match="resolution must be '1k' or '2k'"):
            generate(request)
    resolve.assert_not_called()
    assert "resolution" not in build_request(
        ImageRequest(prompt="draw", model=request.model, aspect="1:1")
    )


def test_auto_aspect_is_never_sent():
    request = ImageRequest(
        prompt="draw", model="grok-imagine-image-2.0", aspect="auto"
    )
    with patch("lith.call.xai.resolve_credential") as resolve, patch(
        "lith.call.xai.post_json"
    ) as post:
        with pytest.raises(InvalidRequest, match="concrete aspect.*never sends 'auto'"):
            generate(request)
    resolve.assert_not_called()
    post.assert_not_called()


def test_resolves_xai_credential_only_when_one_is_not_supplied():
    resolved = credential()
    payload = response(png(10, 10))
    request = ImageRequest(
        prompt="draw", model="grok-imagine-image-2.0", aspect="1:1"
    )
    with (
        patch("lith.call.xai.resolve_credential", return_value=resolved) as resolve,
        patch("lith.call.xai.post_json", return_value=payload),
    ):
        generate(request)
    resolve.assert_called_once_with("xai")

    with (
        patch("lith.call.xai.resolve_credential") as resolve,
        patch("lith.call.xai.post_json", return_value=payload),
    ):
        generate(request, credential=resolved)
    resolve.assert_not_called()


def test_rejects_a_credential_for_another_provider_before_transport():
    request = ImageRequest(
        prompt="draw", model="grok-imagine-image-2.0", aspect="1:1"
    )
    with patch("lith.call.xai.post_json") as post:
        with pytest.raises(ValueError, match="requires an xai credential"):
            generate(request, credential=credential(provider="openai"))
    post.assert_not_called()


def test_oauth_auth_error_tells_the_caller_to_let_hermes_refresh():
    original = AuthError("unauthorized", status_code=401, payload={"error": {}})
    request = ImageRequest(
        prompt="draw", model="grok-imagine-image-2.0", aspect="1:1"
    )
    with patch("lith.call.xai.post_json", side_effect=original):
        with pytest.raises(AuthError) as raised:
            generate(request, credential=credential(oauth=True))
    assert str(raised.value) == "token expired — let Hermes refresh it"
    assert raised.value.status_code == 401
    assert raised.value.payload == {"error": {}}
    assert raised.value.__cause__ is original


def test_api_key_auth_error_is_not_rewritten():
    original = AuthError("bad API key", status_code=401)
    request = ImageRequest(
        prompt="draw", model="grok-imagine-image-2.0", aspect="1:1"
    )
    with patch("lith.call.xai.post_json", side_effect=original):
        with pytest.raises(AuthError) as raised:
            generate(request, credential=credential())
    assert raised.value is original


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "no data list"),
        ({"data": ["not-an-object"]}, "candidate 0 is not an object"),
        ({"data": [{}]}, "candidate 0 has neither b64_json nor url"),
        ({"data": [{"b64_json": "%%%"}]}, "candidate 0 has invalid b64_json"),
    ],
)
def test_invalid_provider_candidate_shapes_are_provider_errors(payload, message):
    request = ImageRequest(
        prompt="draw", model="grok-imagine-image-2.0", aspect="1:1"
    )
    with patch("lith.call.xai.post_json", return_value=payload):
        with pytest.raises(ProviderError, match=message):
            generate(request, credential=credential())


def test_mime_is_inferred_when_xai_does_not_report_it():
    image = png(20, 30)
    payload = {
        "data": [{"b64_json": base64.b64encode(image).decode()}],
        "usage": {},
    }
    request = ImageRequest(
        prompt="draw", model="grok-imagine-image-2.0", aspect="2:3"
    )
    with patch("lith.call.xai.post_json", return_value=payload):
        result = generate(request, credential=credential())
    assert result.candidates[0].mime == "image/png"
    assert result.candidates[0].dimensions == (20, 30)
    assert result.model_reported == "grok-imagine-image-2.0"
    assert result.aspect_reported is None
    assert result.revised_prompt is None
    assert result.cost is None
