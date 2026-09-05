"""Small, provider-neutral JSON transport built on the standard library."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any


DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRY_BACKOFF = 0.5
REDACTED = "<redacted>"
_AUTH_HEADERS = frozenset({"authorization", "proxy-authorization"})


class ProviderError(RuntimeError):
    """A provider or transport failure that has no more specific category."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class AuthError(ProviderError):
    """The credential was absent, invalid, or unauthorized for the request."""


class RateLimited(ProviderError):
    """The provider refused the request because its rate limit was reached."""


class ContentRejected(ProviderError):
    """The provider's content or safety policy rejected the request."""


class InvalidRequest(ProviderError):
    """The provider rejected the shape or values of the request."""


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Copy request headers with credentials replaced by a fixed marker."""
    return {
        key: REDACTED if key.lower() in _AUTH_HEADERS else value
        for key, value in headers.items()
    }


def _request_summary(url: str, headers: Mapping[str, str]) -> str:
    safe_headers = json.dumps(redact_headers(headers), sort_keys=True)
    return f"POST {url} headers={safe_headers}"


def _authorization_values(headers: Mapping[str, str]) -> tuple[str, ...]:
    secrets = set()
    for key, value in headers.items():
        if key.lower() in _AUTH_HEADERS and value:
            secrets.add(value)
            parts = value.split(None, 1)
            if len(parts) == 2:
                secrets.add(parts[1])
    return tuple(sorted(secrets, key=len, reverse=True))


def _redact_text(text: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        text = text.replace(secret, REDACTED)
    return text


def _decode_payload(raw: bytes) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _error_message(payload: dict[str, Any] | None, fallback: str) -> str:
    if not payload:
        return fallback
    error = payload.get("error")
    if isinstance(error, dict):
        parts = [error.get("message"), error.get("type"), error.get("code")]
        text = ": ".join(str(part) for part in parts if part not in (None, ""))
        if text:
            return text
    elif isinstance(error, str) and error:
        return error
    for key in ("message", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return fallback


def _raise_http_error(
    status: int,
    payload: dict[str, Any] | None,
    reason: str,
    summary: str,
    secrets: tuple[str, ...],
) -> None:
    message = _redact_text(_error_message(payload, reason), secrets)
    rendered = f"{summary} failed with HTTP {status}: {message}"
    if status in (401, 403):
        error_type = AuthError
    elif status == 429:
        error_type = RateLimited
    elif status in (400, 404, 409, 422):
        error_type = InvalidRequest
    else:
        error_type = ProviderError
    raise error_type(rendered, status_code=status, payload=payload)


def _check_minimax(
    payload: dict[str, Any], summary: str, secrets: tuple[str, ...]
) -> None:
    base_resp = payload.get("base_resp")
    if not isinstance(base_resp, dict):
        return
    raw_code = base_resp.get("status_code", 0)
    try:
        code = int(raw_code)
    except (TypeError, ValueError):
        code = -1
    if code == 0:
        return

    message = _redact_text(str(base_resp.get("status_msg") or "provider error"), secrets)
    rendered = _redact_text(f"{summary} failed with MiniMax status {raw_code}: {message}", secrets)
    if code in (1004, 2049):
        error_type: type[ProviderError] = AuthError
    elif code == 1002:
        error_type = RateLimited
    elif code == 1026:
        error_type = ContentRejected
    elif code == 2013:
        error_type = InvalidRequest
    else:
        error_type = ProviderError
    raise error_type(rendered, status_code=code, payload=payload)


def post_json(
    url: str,
    body: Mapping[str, Any],
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retry_backoff: float = DEFAULT_RETRY_BACKOFF,
) -> dict[str, Any]:
    """POST a JSON object and return a JSON object.

    HTTP 429 and 5xx responses are retried exactly once. MiniMax application
    errors are mapped after a successful HTTP response because that API reports
    failures inside ``base_resp`` with HTTP 200.
    """
    request_headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    encoded = json.dumps(dict(body)).encode("utf-8")
    summary = _request_summary(url, request_headers)
    secrets = _authorization_values(request_headers)

    for attempt in range(2):
        request = urllib.request.Request(
            url, data=encoded, method="POST"
        )
        for key, value in request_headers.items():
            if key.lower() in _AUTH_HEADERS:
                # urllib copies ordinary headers onto redirected requests.
                request.add_unredirected_header(key, value)
            else:
                request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                reason = str(getattr(response, "reason", "provider error"))
                raw = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            reason = str(exc.reason)
            with exc:
                raw = exc.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            reason = _redact_text(str(getattr(exc, "reason", exc)), secrets)
            raise ProviderError(f"{summary} failed: {reason}") from exc

        payload = _decode_payload(raw)
        retryable = status == 429 or 500 <= status <= 599
        if retryable and attempt == 0:
            time.sleep(retry_backoff)
            continue
        if status >= 400:
            _raise_http_error(status, payload, reason, summary, secrets)
        if payload is None:
            raise ProviderError(
                f"{summary} returned a non-object or invalid JSON response",
                status_code=status,
            )
        _check_minimax(payload, summary, secrets)
        return payload

    raise AssertionError("unreachable")
