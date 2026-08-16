import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from lith.call.http import (
    AuthError,
    ContentRejected,
    InvalidRequest,
    ProviderError,
    RateLimited,
    post_json,
    redact_headers,
)


class Response:
    def __init__(self, payload, *, status=200, reason="OK"):
        self.body = json.dumps(payload).encode()
        self.status = status
        self.reason = reason

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body


def http_error(status, payload, reason="failed"):
    return urllib.error.HTTPError(
        "https://provider.test/v1/images",
        status,
        reason,
        {},
        io.BytesIO(json.dumps(payload).encode()),
    )


def test_post_json_sends_json_headers_and_timeout():
    response = {"data": [{"b64_json": "abc"}]}
    with patch("urllib.request.urlopen", return_value=Response(response)) as urlopen:
        assert post_json(
            "https://provider.test/v1/images",
            {"prompt": "draw this"},
            headers={"Authorization": "Bearer secret"},
            timeout=7,
        ) == response

    request = urlopen.call_args.args[0]
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"prompt": "draw this"}
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("Authorization") == "Bearer secret"
    assert urlopen.call_args.kwargs == {"timeout": 7}


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retries_429_and_5xx_exactly_once(status):
    first = http_error(status, {"error": {"message": "try later"}})
    with (
        patch("urllib.request.urlopen", side_effect=[first, Response({"data": []})]) as urlopen,
        patch("time.sleep") as sleep,
    ):
        assert post_json("https://provider.test/v1/images", {}, retry_backoff=0.25) == {
            "data": []
        }
    assert urlopen.call_count == 2
    sleep.assert_called_once_with(0.25)


@pytest.mark.parametrize(
    ("status", "expected"),
    [(429, RateLimited), (500, ProviderError)],
)
def test_retryable_http_failure_is_raised_after_one_retry(status, expected):
    errors = [
        http_error(status, {"error": {"message": "still failing"}}),
        http_error(status, {"error": {"message": "still failing"}}),
    ]
    with patch("urllib.request.urlopen", side_effect=errors) as urlopen, patch("time.sleep"):
        with pytest.raises(expected):
            post_json("https://provider.test/v1/images", {})
    assert urlopen.call_count == 2


@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (401, {"error": {"message": "bad xAI token"}}, AuthError),
        (403, {"error": {"message": "forbidden"}}, AuthError),
        (400, {"error": {"message": "bad size", "type": "invalid_request_error"}}, InvalidRequest),
        (422, {"error": {"message": "invalid aspect_ratio"}}, InvalidRequest),
        (
            400,
            {"error": {"message": "blocked", "code": "content_policy_violation"}},
            ContentRejected,
        ),
        (
            400,
            {"error": {"message": "request rejected by content moderation"}},
            ContentRejected,
        ),
    ],
)
def test_maps_xai_and_openai_http_error_shapes(status, payload, expected):
    with patch("urllib.request.urlopen", side_effect=http_error(status, payload)):
        with pytest.raises(expected) as raised:
            post_json("https://provider.test/v1/images", {})
    assert raised.value.status_code == status
    assert raised.value.payload == payload


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"error": "plain provider error"}, "plain provider error"),
        ({"message": "top-level message"}, "top-level message"),
        ({"detail": "top-level detail"}, "top-level detail"),
        ({"unexpected": True}, "Bad Request"),
    ],
)
def test_renders_other_provider_error_message_shapes(payload, message):
    error = http_error(400, payload, reason="Bad Request")
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(InvalidRequest, match=message):
            post_json("https://provider.test/v1/images", {})


def test_non_json_http_error_uses_the_http_reason():
    error = urllib.error.HTTPError(
        "https://provider.test/v1/images",
        400,
        "Bad Request",
        {},
        io.BytesIO(b"not json"),
    )
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(InvalidRequest, match="Bad Request"):
            post_json("https://provider.test/v1/images", {})


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
def test_maps_minimax_errors_inside_http_200(code, expected):
    payload = {
        "base_resp": {"status_code": code, "status_msg": "fixture failure"},
        "data": {},
    }
    with patch("urllib.request.urlopen", return_value=Response(payload)):
        with pytest.raises(expected) as raised:
            post_json("https://api.minimax.io/v1/image_generation", {})
    assert raised.value.status_code == code
    assert raised.value.payload == payload


def test_minimax_zero_status_is_success():
    payload = {"base_resp": {"status_code": 0, "status_msg": "success"}, "data": {}}
    with patch("urllib.request.urlopen", return_value=Response(payload)):
        assert post_json("https://api.minimax.io/v1/image_generation", {}) == payload


def test_unknown_minimax_status_is_a_provider_error():
    payload = {"base_resp": {"status_code": "unknown"}, "data": {}}
    with patch("urllib.request.urlopen", return_value=Response(payload)):
        with pytest.raises(ProviderError) as raised:
            post_json("https://api.minimax.io/v1/image_generation", {})
    assert raised.value.status_code == -1


def test_authorization_is_redacted_from_rendered_diagnostics():
    secret = "Bearer never-print-this"
    payload = {"error": {"message": f"credential {secret} was rejected"}}
    with patch("urllib.request.urlopen", side_effect=http_error(401, payload)):
        with pytest.raises(AuthError) as raised:
            post_json(
                "https://provider.test/v1/images",
                {},
                headers={"authorization": secret, "X-Trace": "visible"},
            )
    rendered = str(raised.value)
    assert secret not in rendered
    assert "never-print-this" not in rendered
    assert "<redacted>" in rendered
    assert "visible" in rendered
    assert redact_headers({"Proxy-Authorization": secret}) == {
        "Proxy-Authorization": "<redacted>"
    }


def test_network_failure_and_invalid_json_are_provider_errors():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
        with pytest.raises(ProviderError, match="offline"):
            post_json("https://provider.test/v1/images", {})

    response = Response({})
    response.body = b"not json"
    with patch("urllib.request.urlopen", return_value=response):
        with pytest.raises(ProviderError, match="invalid JSON"):
            post_json("https://provider.test/v1/images", {})
