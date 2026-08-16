from dataclasses import FrozenInstanceError, fields
from types import SimpleNamespace

import pytest

from lith.call import CallResult, Candidate, ImageRequest, generate
from lith.call.capability import MODEL_PROVIDERS, provider_for_model


def test_image_request_has_the_uniform_fields_and_defaults():
    request = ImageRequest(prompt="draw this", model="gpt-image-2", aspect="20:9")
    assert [field.name for field in fields(ImageRequest)] == [
        "prompt",
        "model",
        "aspect",
        "n",
        "seed",
        "resolution",
        "quality",
        "background",
        "negative_prompt",
    ]
    assert request.n == 1
    assert request.seed is None
    assert request.resolution is None
    assert request.quality is None
    assert request.background is None
    assert request.negative_prompt is None
    with pytest.raises(FrozenInstanceError):
        request.prompt = "changed"


def test_candidate_and_call_result_preserve_provider_evidence():
    candidate = Candidate(index=0, data=b"image", mime="image/png", dimensions=(2, 3))
    raw = {"data": [{"b64_json": "redacted in a provider adapter"}]}
    result = CallResult(
        candidates=[candidate],
        model_reported="grok-imagine-image-2.0",
        aspect_reported="2:3",
        revised_prompt="",
        unsupported={"negative_prompt": "xAI does not accept this field"},
        cost="123",
        raw=raw,
    )
    assert result.candidates == [candidate]
    assert result.model_reported == "grok-imagine-image-2.0"
    assert result.aspect_reported == "2:3"
    assert result.revised_prompt == ""
    assert result.unsupported == {
        "negative_prompt": "xAI does not accept this field"
    }
    assert result.cost == "123"
    assert result.raw is raw


def test_all_capability_models_map_to_a_provider():
    from lith.aspect import MODEL_ASPECTS

    assert MODEL_PROVIDERS == {
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
    assert set(MODEL_PROVIDERS) == set(MODEL_ASPECTS)
    for model, provider in MODEL_PROVIDERS.items():
        assert provider_for_model(model) == provider


@pytest.mark.parametrize(
    ("model", "provider"),
    [
        ("grok-imagine-image-2.0", "xai"),
        ("grok-imagine-image-quality", "xai"),
        ("grok-imagine-image", "xai"),
        ("gpt-image-2", "openai"),
        ("image-01", "minimax"),
    ],
)
def test_generate_lazily_dispatches_without_transport(model, provider, monkeypatch):
    request = ImageRequest(prompt="draw this", model=model, aspect="1:1")
    expected = CallResult([], model, "1:1", None, {}, None, {"provider": provider})
    imported = []

    def fake_import(name):
        imported.append(name)

        def fake_generate(received, *, credential):
            assert received is request
            assert credential is None
            return expected

        return SimpleNamespace(generate=fake_generate)

    monkeypatch.setattr("lith.call.import_module", fake_import)
    assert generate(request) is expected
    assert imported == [f"lith.call.{provider}"]


def test_generate_passes_an_explicit_credential_to_the_adapter(monkeypatch):
    request = ImageRequest(prompt="draw this", model="gpt-image-2", aspect="1:1")
    credential = object()

    def fake_import(_name):
        def fake_generate(received, *, credential: object):
            assert received is request
            assert credential is not None
            return CallResult([], None, None, None, {}, None, {})

        return SimpleNamespace(generate=fake_generate)

    monkeypatch.setattr("lith.call.import_module", fake_import)
    assert generate(request, credential=credential).candidates == []


def test_generate_rejects_an_unknown_model_before_import(monkeypatch):
    def unexpected_import(name):
        raise AssertionError(f"must not import an adapter for {name}")

    monkeypatch.setattr("lith.call.import_module", unexpected_import)
    request = ImageRequest(prompt="draw this", model="future-image-9", aspect="1:1")
    with pytest.raises(ValueError) as caught:
        generate(request)
    message = str(caught.value)
    assert "unknown image model 'future-image-9'" in message
    assert "grok-imagine-image-2.0" in message
    assert "image-01" in message
