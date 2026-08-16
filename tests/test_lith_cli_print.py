import subprocess
import struct
import sys
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO = Path(__file__).resolve().parents[1]


def png(width, height):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = zlib.compress((b"\x00" + b"\x20\x80\x40" * width) * height)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


def test_dry_mode_prints_plan():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lith.cli.print",
            "--recipe",
            str(REPO / "recipes" / "live_test_recipe.json"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "DILL PICKLES" in out
    assert "Next:" in out


def test_download_rejects_non_http_schemes():
    from lith.imagebytes import download

    with pytest.raises(ValueError, match="refusing to fetch scheme"):
        download("file:///etc/passwd", Path("/tmp/x.jpg"))


def test_download_rejects_oversized_response(tmp_path):
    from lith.imagebytes import download

    fake = MagicMock()
    fake.url = "http://example.com/huge.jpg"
    fake.headers = {"Content-Type": "image/jpeg"}
    big = b"\xff\xd8\xff" + b"x" * (1024 * 1024)

    def chunk_iter():
        for _ in range(30):
            yield big

    fake.__enter__ = lambda self: self
    fake.__exit__ = lambda self, *args: None
    fake.__iter__ = lambda self: chunk_iter()
    with patch("urllib.request.urlopen", return_value=fake):
        with pytest.raises(ValueError, match="exceeds"):
            download("http://example.com/huge.jpg", tmp_path / "x.jpg")


def test_download_rejects_redirect_to_disallowed_scheme(tmp_path):
    from lith.imagebytes import download

    fake = MagicMock()
    fake.url = "ftp://example.com/image.jpg"
    fake.__enter__ = lambda self: self
    fake.__exit__ = lambda self, *args: None

    with patch("urllib.request.urlopen", return_value=fake):
        with pytest.raises(ValueError, match="refusing redirected scheme 'ftp'"):
            download("https://example.com/image.jpg", tmp_path / "x.jpg")


def test_publishes_under_the_recipe_name(tmp_path):
    """The model's image is the deliverable; no staging file survives."""
    src = tmp_path / "candidate.png"
    src.write_bytes(png(16, 16))
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "lith.cli.print",
         "--recipe", str(REPO / "recipes" / "live_test_recipe.json"),
         "--output-dir", str(out), "--image-file", str(src)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (out / "B_brutalist_dill_pickles.png").is_file()
    assert not list(out.glob("*.part"))


def test_image_size_reads_jpeg_and_png_headers():
    from lith.imagebytes import image_size

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + (1024).to_bytes(4, "big") + (1536).to_bytes(4, "big")
    assert image_size(png) == (1024, 1536)
    # Minimal JPEG: SOI, then an SOF0 declaring 720x1280.
    jpeg = b"\xff\xd8\xff" + b"\xe0\x00\x02" + b"\xff\xc0\x00\x11\x08" + (1280).to_bytes(2, "big") + (720).to_bytes(2, "big") + b"\x00" * 8
    assert image_size(jpeg) == (720, 1280)
    assert image_size(b"RIFF____WEBP") is None  # unparsed on purpose


def test_public_image_helpers_share_magic_byte_detection():
    from lith.imagebytes import image_ext, looks_like_image

    truncated = b"\x89PNG\r\n\x1a\nfixture"
    assert image_ext(truncated) == ".png"
    assert not looks_like_image(truncated)
    assert looks_like_image(png(1, 1))
    assert image_ext(b"not an image") is None
    assert not looks_like_image(b"not an image")


def test_strict_exits_nonzero_on_frame_drift(tmp_path):
    """A warning alone let 18 reframed images publish as a clean sweep."""
    # The canary recipe asks 1:1; hand it a 9:16 portrait.
    src = tmp_path / "candidate.png"
    src.write_bytes(png(72, 128))
    argv = [sys.executable, "-m", "lith.cli.print",
            "--recipe", str(REPO / "recipes" / "live_test_recipe.json"),
            "--output-dir", str(tmp_path / "out"), "--image-file", str(src)]

    lax = subprocess.run(argv, capture_output=True, text=True)
    assert lax.returncode == 0
    assert "aspect:" in lax.stdout

    strict = subprocess.run(argv + ["--strict"], capture_output=True, text=True)
    assert strict.returncode == 1, strict.stdout
    # Published anyway: the bytes are the evidence for diagnosing the drift.
    assert (tmp_path / "out" / "B_brutalist_dill_pickles.png").is_file()


def test_strict_stays_silent_when_the_frame_matches(tmp_path):
    src = tmp_path / "candidate.png"
    src.write_bytes(png(128, 128))
    result = subprocess.run(
        [sys.executable, "-m", "lith.cli.print",
         "--recipe", str(REPO / "recipes" / "live_test_recipe.json"),
         "--output-dir", str(tmp_path / "out"), "--image-file", str(src),
         "--strict"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout


def test_aspect_mismatch_flags_a_silent_substitution():
    from lith.cli.print import aspect_mismatch

    portrait = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + (720).to_bytes(4, "big") + (1280).to_bytes(4, "big")
    # 720x1280 is 9:16. Asking for 2:3 and getting this is the real defect.
    assert aspect_mismatch(portrait, "2:3")
    assert aspect_mismatch(portrait, "9:16") is None
    # Unparseable or absent requests never raise.
    assert aspect_mismatch(b"RIFF____WEBP", "2:3") is None
    assert aspect_mismatch(portrait, "auto") is None
    assert aspect_mismatch(portrait, "0:0") is None
