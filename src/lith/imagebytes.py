"""Utilities for downloading and inspecting image bytes."""

from __future__ import annotations

import pathlib
import struct
import urllib.parse
import urllib.request


ALLOWED_SCHEMES = ("http", "https")
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_MAX_BYTES = 25 * 1024 * 1024
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _looks_like_image(body: bytes) -> bool:
    return _image_ext(body) is not None


def _image_size(body: bytes) -> tuple[int, int] | None:
    """Read pixel dimensions from a PNG or JPEG header.

    ponytail: WebP is not parsed — it has three container variants and no
    model in the CLI's list returns it. Returns None, and the caller skips
    the aspect check rather than guessing.
    """
    if body.startswith(PNG_MAGIC):
        return struct.unpack(">II", body[16:24])
    if not body.startswith(JPEG_MAGIC):
        return None
    i = 2
    while i + 9 < len(body):
        if body[i] != 0xFF:
            i += 1
            continue
        marker = body[i + 1]
        # SOF0/1/2/3 and SOF5..15 carry the frame size; skip SOF4/12 (DHT/DAC).
        if marker in (0xC0, 0xC1, 0xC2, 0xC3) or 0xC5 <= marker <= 0xCF:
            height, width = struct.unpack(">HH", body[i + 5 : i + 9])
            return width, height
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        i += 2 + struct.unpack(">H", body[i + 2 : i + 4])[0]
    return None


def _image_ext(body: bytes) -> str | None:
    if body.startswith(JPEG_MAGIC):
        return ".jpg"
    if body.startswith(PNG_MAGIC):
        return ".png"
    if body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        return ".webp"
    return None


def download(url: str, dst: pathlib.Path) -> pathlib.Path:
    """Fetch an HTTP(S) model-generated image with size and format guards."""
    parsed = urllib.parse.urlsplit(url)
    if not parsed.scheme:
        raise ValueError(f"refusing to fetch non-URL: {url!r}")
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(
            f"refusing to fetch scheme {scheme!r}; allowed: {ALLOWED_SCHEMES}"
        )
    if not parsed.netloc:
        raise ValueError(f"refusing to fetch non-URL: {url!r}")

    req = urllib.request.Request(url, headers={"User-Agent": "lith/1.0"})
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as response:
        response_scheme = urllib.parse.urlsplit(response.url).scheme.lower()
        if response_scheme not in ALLOWED_SCHEMES:
            raise ValueError(
                f"refusing redirected scheme {response_scheme!r}; "
                f"allowed: {ALLOWED_SCHEMES}"
            )
        chunks = []
        total = 0
        for chunk in response:
            total += len(chunk)
            if total > DOWNLOAD_MAX_BYTES:
                raise ValueError(
                    f"download exceeds {DOWNLOAD_MAX_BYTES} bytes; aborting"
                )
            chunks.append(chunk)
        body = b"".join(chunks)

    if not _looks_like_image(body):
        raise ValueError("downloaded bytes do not look like an image (magic mismatch)")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(body)
    return dst
