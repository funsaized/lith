"""Utilities for downloading and inspecting image bytes."""

from __future__ import annotations

import pathlib
import struct
import urllib.parse
import urllib.request
import zlib


ALLOWED_SCHEMES = ("http", "https")
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_MAX_BYTES = 25 * 1024 * 1024
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def looks_like_image(body: bytes) -> bool:
    """Return whether the complete byte string is a structurally valid image."""
    extension = image_ext(body)
    if extension == ".png":
        return _valid_png(body)
    if extension == ".jpg":
        return (
            body.endswith(b"\xff\xd9")
            and b"\xff\xda" in body
            and image_size(body) is not None
        )
    if extension == ".webp":
        return _valid_webp(body)
    return False


def _webp_chunks(body: bytes):
    if len(body) < 12 or struct.unpack("<I", body[4:8])[0] + 8 != len(body):
        return
    offset = 12
    while offset + 8 <= len(body):
        kind = body[offset : offset + 4]
        length = struct.unpack("<I", body[offset + 4 : offset + 8])[0]
        start = offset + 8
        end = start + length
        padded_end = end + (length & 1)
        if end > len(body) or padded_end > len(body):
            return
        yield kind, body[start:end]
        offset = padded_end
    if offset != len(body):
        return


def _webp_dimensions(body: bytes) -> tuple[int, int] | None:
    for kind, payload in _webp_chunks(body) or ():
        if kind == b"VP8 " and len(payload) >= 10 and payload[3:6] == b"\x9d\x01\x2a":
            width, height = struct.unpack("<HH", payload[6:10])
            return width & 0x3FFF, height & 0x3FFF
        if kind == b"VP8L" and len(payload) >= 5 and payload[0] == 0x2F:
            packed = int.from_bytes(payload[1:5], "little")
            return (packed & 0x3FFF) + 1, ((packed >> 14) & 0x3FFF) + 1
        if kind == b"VP8X" and len(payload) == 10:
            width = int.from_bytes(payload[4:7], "little") + 1
            height = int.from_bytes(payload[7:10], "little") + 1
            return width, height
    return None


def _valid_webp(body: bytes) -> bool:
    chunks = list(_webp_chunks(body) or ())
    return bool(
        chunks
        and any(kind in {b"VP8 ", b"VP8L"} for kind, _ in chunks)
        and _webp_dimensions(body) is not None
    )


def _valid_png(body: bytes) -> bool:
    if len(body) < 33:
        return False
    offset = len(PNG_MAGIC)
    kinds: list[bytes] = []
    lengths: list[int] = []
    image_data: list[bytes] = []
    while offset + 12 <= len(body):
        length = struct.unpack(">I", body[offset : offset + 4])[0]
        kind = body[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(body):
            return False
        payload = body[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", body[offset + 8 + length : end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected_crc:
            return False
        kinds.append(kind)
        lengths.append(length)
        if kind == b"IDAT":
            image_data.append(payload)
        offset = end
        if kind == b"IEND":
            break
    try:
        zlib.decompress(b"".join(image_data))
    except zlib.error:
        return False
    return bool(
        offset == len(body)
        and kinds[:1] == [b"IHDR"]
        and lengths[:1] == [13]
        and len(body[16:24]) == 8
        and all(image_size(body))
        and b"IDAT" in kinds
        and kinds[-1:] == [b"IEND"]
        and lengths[-1:] == [0]
    )


def image_size(body: bytes) -> tuple[int, int] | None:
    """Read pixel dimensions from PNG, JPEG, and VP8/VP8L/VP8X WebP headers."""
    if body.startswith(PNG_MAGIC):
        if len(body) < 24:
            return None
        return struct.unpack(">II", body[16:24])
    if body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        return _webp_dimensions(body)
    if not body.startswith(JPEG_MAGIC):
        return None
    i = 2
    while i + 9 < len(body):
        if body[i] != 0xFF:
            i += 1
            continue
        marker = body[i + 1]
        # SOF0/1/2/3 and SOF5..15 carry the frame size; skip SOF4/12 (DHT/DAC).
        if marker in (0xC0, 0xC1, 0xC2, 0xC3) or 0xC5 <= marker <= 0xCB or 0xCD <= marker <= 0xCF:
            if i + 9 > len(body):
                return None
            height, width = struct.unpack(">HH", body[i + 5 : i + 9])
            return width, height
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if i + 4 > len(body):
            return None
        length = struct.unpack(">H", body[i + 2 : i + 4])[0]
        if length < 2:
            return None
        i += 2 + length
    return None


def image_ext(body: bytes) -> str | None:
    if body.startswith(JPEG_MAGIC):
        return ".jpg"
    if body.startswith(PNG_MAGIC):
        return ".png"
    if body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        return ".webp"
    return None


def fetch_image(url: str) -> bytes:
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

    if not looks_like_image(body):
        raise ValueError("downloaded bytes do not look like an image (magic mismatch)")

    return body


def download(url: str, dst: pathlib.Path) -> pathlib.Path:
    """Fetch an image into ``dst`` after validating its URL, size, and bytes."""
    body = fetch_image(url)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(body)
    return dst
