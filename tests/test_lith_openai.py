import base64
from unittest.mock import patch

import pytest

from lith.call import ImageRequest
from lith.call.creds import Credential
from lith.call.http import InvalidRequest, ProviderError
from lith.call.openai import (
    GENERATIONS_URL,
    GENERATION_TIMEOUT,
    build_request,
    generate,
)


def credential(*, provider="openai", organization=None, project=None):
    return Credential(
        provider=provider,
        secret="fixture-secret",
        tier=1,
        source="fixture",
        auth_type="api_key",
        organization_id=organization,
        project_id=project,
    )


def png(width, height):
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00" * 8
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
    )


def response(*images, revised_prompt=None, model=None):
    payload = {
        "data": [
            {
                "b64_json": base64.b64encode(image).decode(),
                **(
                    {"revised_prompt": revised_prompt}
                    if revised_prompt is not None
                    else {}
                ),
            }
            for image in images
        ]
    }
    if model is not None:
        payload["model"] = model
    return payload


def test_fixed_1x_and_constrained_gpt_image_2_use_different_size_strategies():
    common = {
        "prompt": "same authored prompt",
        "aspect": "20:9",
        "n": 2,
        "quality": "high",
        "background": "transparent",
    }
    fixed = build_request(ImageRequest(model="gpt-image-1", **common))
    ranged = build_request(ImageRequest(model="gpt-image-2", **common))

    assert fixed == {
        "model": "gpt-image-1",
        "prompt": "same authored prompt",
        "n": 2,
        "size": "1536x1024",
        "output_format": "png",
        "moderation": "auto",
        "quality": "high",
        "background": "transparent",
    }
    assert ranged == {
        **fixed,
        "model": "gpt-image-2",
        "size": "1280x576",
    }


def test_webp_compression_and_low_moderation_are_explicit_options():
    request = ImageRequest(
        prompt="draw", model="gpt-image-2-2026-04-21", aspect="16:9"
    )
    assert build_request(
        request, output_format="webp", output_compression=72, moderation="low"
    ) == {
        "model": "gpt-image-2-2026-04-21",
        "prompt": "draw",
        "n": 1,
        "size": "1280x720",
        "output_format": "webp",
        "moderation": "low",
        "output_compression": 72,
    }


def test_exact_post_headers_and_parsed_result():
    image = png(1280, 576)
    payload = response(image, revised_prompt="rewritten", model="gpt-image-2")
    request = ImageRequest(
        prompt="draw this byte-for-byte",
        model="gpt-image-2",
        aspect="20:9",
    )
    resolved = credential(organization="org-example", project="project-example")

    with patch("lith.call.openai.post_json", return_value=payload) as post:
        result = generate(request, credential=resolved)

    post.assert_called_once_with(
        GENERATIONS_URL,
        build_request(request),
        headers={
            "Authorization": "Bearer fixture-secret",
            "OpenAI-Organization": "org-example",
            "OpenAI-Project": "project-example",
        },
        timeout=GENERATION_TIMEOUT,
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].index == 0
    assert result.candidates[0].data == image
    assert result.candidates[0].mime == "image/png"
    assert result.candidates[0].dimensions == (1280, 576)
    assert result.model_reported == "gpt-image-2"
    assert result.aspect_reported is None
    assert result.revised_prompt == "rewritten"
    assert result.unsupported == {}
    assert result.cost is None
    assert result.raw is payload


def test_unsupported_fields_are_reported_without_touching_prompt():
    prompt = "POSITIVE ONLY\nDo not mutate this exact string."
    request = ImageRequest(
        prompt=prompt,
        model="gpt-image-2",
        aspect="1:1",
        resolution="2k",
        seed=0,
        negative_prompt="words, watermarks",
    )
    with patch(
        "lith.call.openai.post_json", return_value=response(png(816, 816))
    ) as post:
        result = generate(request, credential=credential())

    sent = post.call_args.args[1]
    assert sent["prompt"] == prompt
    assert "words, watermarks" not in sent["prompt"]
    assert "resolution" not in sent
    assert "seed" not in sent
    assert "negative_prompt" not in sent
    assert result.unsupported == {
        "resolution": "OpenAI image generation accepts size, not resolution",
        "seed": "OpenAI image generation does not accept seed",
        "negative_prompt": "OpenAI image generation does not accept negative_prompt",
    }


@pytest.mark.parametrize("n", [0, 11, True, 1.5])
def test_n_must_be_an_integer_from_one_through_ten(n):
    request = ImageRequest(prompt="draw", model="gpt-image-2", aspect="1:1", n=n)
    with patch("lith.call.openai.resolve_credential") as resolve:
        with pytest.raises(InvalidRequest, match="integer from 1 through 10"):
            generate(request)
    resolve.assert_not_called()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"output_format": "gif"}, "output_format"),
        ({"moderation": "strict"}, "moderation"),
        ({"output_compression": -1}, "output_compression"),
        ({"output_compression": 101}, "output_compression"),
        ({"output_compression": True}, "output_compression"),
        ({"output_compression": 50}, "only with jpeg or webp"),
    ],
)
def test_output_options_are_validated_before_auth(kwargs, message):
    request = ImageRequest(prompt="draw", model="gpt-image-2", aspect="1:1")
    with patch("lith.call.openai.resolve_credential") as resolve:
        with pytest.raises(InvalidRequest, match=message):
            generate(request, **kwargs)
    resolve.assert_not_called()


@pytest.mark.parametrize(
    "image_request",
    [
        ImageRequest(
            prompt="draw", model="gpt-image-2", aspect="1:1", quality="ultra"
        ),
        ImageRequest(
            prompt="draw", model="gpt-image-2", aspect="1:1", background="alpha"
        ),
        ImageRequest(
            prompt="draw", model="gpt-image-2", aspect="auto"
        ),
        ImageRequest(
            prompt="draw", model="grok-imagine-image-2.0", aspect="1:1"
        ),
    ],
)
def test_request_values_are_validated_before_auth(image_request):
    with patch("lith.call.openai.resolve_credential") as resolve:
        with pytest.raises(InvalidRequest):
            generate(image_request)
    resolve.assert_not_called()


def test_resolves_openai_credential_only_when_not_supplied():
    request = ImageRequest(prompt="draw", model="gpt-image-2", aspect="1:1")
    resolved = credential()
    payload = response(png(816, 816))
    with (
        patch("lith.call.openai.resolve_credential", return_value=resolved) as resolve,
        patch("lith.call.openai.post_json", return_value=payload),
    ):
        generate(request)
    resolve.assert_called_once_with("openai")

    with (
        patch("lith.call.openai.resolve_credential") as resolve,
        patch("lith.call.openai.post_json", return_value=payload),
    ):
        generate(request, credential=resolved)
    resolve.assert_not_called()


def test_rejects_a_credential_for_another_provider_before_transport():
    request = ImageRequest(prompt="draw", model="gpt-image-2", aspect="1:1")
    with patch("lith.call.openai.post_json") as post:
        with pytest.raises(ValueError, match="requires an openai credential"):
            generate(request, credential=credential(provider="xai"))
    post.assert_not_called()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "no data list"),
        ({"data": ["not-an-object"]}, "candidate 0 is not an object"),
        ({"data": [{}]}, "candidate 0 has no b64_json"),
        ({"data": [{"b64_json": "%%%"}]}, "candidate 0 has invalid b64_json"),
    ],
)
def test_invalid_provider_candidate_shapes_are_provider_errors(payload, message):
    request = ImageRequest(prompt="draw", model="gpt-image-2", aspect="1:1")
    with patch("lith.call.openai.post_json", return_value=payload):
        with pytest.raises(ProviderError, match=message):
            generate(request, credential=credential())


def test_requested_format_supplies_mime_fallback_and_model_falls_back_to_request():
    data = b"not enough bytes for magic sniffing"
    request = ImageRequest(prompt="draw", model="gpt-image-1.5", aspect="1:1")
    with patch(
        "lith.call.openai.post_json",
        return_value=response(data),
    ):
        result = generate(request, credential=credential(), output_format="jpeg")
    assert result.candidates[0].mime == "image/jpeg"
    assert result.candidates[0].dimensions is None
    assert result.model_reported == "gpt-image-1.5"
    assert result.revised_prompt is None
