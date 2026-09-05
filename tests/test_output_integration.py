"""Output integration coverage with complete image containers and failure cases."""

import base64
import json
import io
import pathlib
import struct
import sys
import zlib

import pytest

from lith.call import CallResult, Candidate
from lith.cli import press as press_cli
from lith.cli import print as print_cli
from lith.imagebytes import fetch_image, image_size, looks_like_image


WEBP_1X1 = base64.b64decode(
    "UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAAgA0JaQAA3AA/vv9UAA="
)
pytestmark = pytest.mark.integration


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def png(width: int, height: int, *, shade: int = 80) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    scanline = b"\x00" + bytes([shade, 120, 40]) * width
    pixels = zlib.compress(scanline * height)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", pixels) + _chunk(b"IEND", b"")


def _recipe(tmp_path, *, aspect="2:3"):
    path = tmp_path / "dill-pickles.json"
    path.write_text(
        json.dumps(
            {
                "name": "dill-output",
                "style": "B",
                "model": "grok-imagine-image-2.0",
                "n": 1,
                "brief": {
                    "topic": "Why dill pickles make every sandwich better",
                    "headline": "DILL PICKLES",
                    "icon": "lightning",
                    "aspect": aspect,
                    "sections": [
                        {
                            "heading": "THE CRUNCH",
                            "lines": ["Cold brine keeps every spear crisp"],
                        }
                    ],
                },
            }
        )
    )
    return path


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["lith-print", *map(str, argv)])
    return print_cli.main()


class Response:
    def __init__(self, body: bytes, url="https://cdn.example/final.png"):
        self.body = io.BytesIO(body)
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size):
        assert 0 < size <= 64 * 1024
        return self.body.read(size)


@pytest.mark.parametrize(
    ("extension", "body", "dimensions"),
    [
        ("png", png(20, 30), (20, 30)),
        ("webp", WEBP_1X1, (1, 1)),
    ],
)
def test_complete_generated_formats_publish_with_magic_derived_names(
    extension, body, dimensions, tmp_path, monkeypatch
):
    recipe = _recipe(tmp_path, aspect="1:1" if extension == "webp" else "2:3")
    source = tmp_path / "candidate.wrong-extension"
    source.write_bytes(body)
    output = tmp_path / "published"
    assert _run(monkeypatch, "--recipe", recipe, "--image-file", source, "--output-dir", output, "--strict") == 0
    published = output / f"B_brutalist_dill_pickles.{extension}"
    assert published.read_bytes() == body
    assert looks_like_image(body)
    assert image_size(body) == dimensions


def test_complete_jpeg_fixture_publishes(tmp_path, monkeypatch):
    source = pathlib.Path(__file__).resolve().parents[1] / "outputs" / "B_brutalist_32_langs_raw.jpg"
    recipe = _recipe(tmp_path, aspect="16:9")
    output = tmp_path / "published"
    assert _run(monkeypatch, "--recipe", recipe, "--image-file", source, "--output-dir", output, "--strict") == 0
    assert (output / "B_brutalist_dill_pickles.jpg").read_bytes() == source.read_bytes()


@pytest.mark.parametrize(
    "body",
    [
        png(2, 3)[:-5],
        b"\xff\xd8\xff\xe0truncated jpeg",
        WEBP_1X1[:-1],
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 24,
    ],
)
def test_truncated_or_corrupt_images_never_publish(body, tmp_path, monkeypatch):
    recipe = _recipe(tmp_path)
    source = tmp_path / "corrupt.img"
    source.write_bytes(body)
    output = tmp_path / "published"
    with pytest.raises(ValueError, match="not a recognized image format"):
        _run(monkeypatch, "--recipe", recipe, "--image-file", source, "--output-dir", output)
    assert not output.exists()


def test_remote_url_and_https_redirect_publish_validated_bytes(tmp_path, monkeypatch):
    body = png(20, 30)
    seen = {}

    def urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return Response(body, "https://images.example/redirected.png")

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    recipe = _recipe(tmp_path)
    output = tmp_path / "remote"
    assert _run(
        monkeypatch,
        "--recipe", recipe,
        "--image-url", "https://provider.example/candidate",
        "--output-dir", output,
        "--strict",
    ) == 0
    assert seen["url"] == "https://provider.example/candidate"
    assert (output / "B_brutalist_dill_pickles.png").read_bytes() == body


def test_remote_redirect_and_oversize_fail_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response(png(1, 1), "file:///tmp/pickle.png"))
    with pytest.raises(ValueError, match="redirected scheme"):
        fetch_image("https://provider.example/redirect")

    monkeypatch.setattr("lith.imagebytes.DOWNLOAD_MAX_BYTES", 8)
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response(png(1, 1)))
    with pytest.raises(ValueError, match="download exceeds"):
        fetch_image("https://provider.example/huge")


def test_strict_aspect_pass_and_fail_are_observable(tmp_path, monkeypatch, capsys):
    recipe = _recipe(tmp_path)
    good = tmp_path / "good.png"
    bad = tmp_path / "bad.png"
    good.write_bytes(png(20, 30))
    bad.write_bytes(png(30, 20))
    assert _run(monkeypatch, "--recipe", recipe, "--image-file", good, "--output-dir", tmp_path / "good", "--strict") == 0
    assert "[fail]" not in capsys.readouterr().out
    assert _run(monkeypatch, "--recipe", recipe, "--image-file", bad, "--output-dir", tmp_path / "bad", "--strict") == 1
    assert "[fail]" in capsys.readouterr().out


def test_candidate_batch_is_atomic_and_existing_output_warns_on_overwrite(
    tmp_path, monkeypatch, capsys
):
    valid = png(20, 30)
    invalid_batch = CallResult(
        [Candidate(0, valid, "image/png", (20, 30)), Candidate(1, valid[:-4], "image/png", None)],
        None, None, None, {}, None, {},
    )
    candidate_dir = tmp_path / "candidates"
    with pytest.raises(ValueError, match="candidate 1"):
        press_cli._write_candidates(
            invalid_batch,
            output_dir=candidate_dir,
            family_key="B_brutalist",
            headline="DILL PICKLES",
        )
    assert not candidate_dir.exists()

    recipe = _recipe(tmp_path)
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(png(20, 30, shade=20))
    second.write_bytes(png(20, 30, shade=220))
    output = tmp_path / "overwrite"
    assert _run(monkeypatch, "--recipe", recipe, "--image-file", first, "--output-dir", output) == 0
    capsys.readouterr()
    assert _run(monkeypatch, "--recipe", recipe, "--image-file", second, "--output-dir", output) == 0
    captured = capsys.readouterr().out
    published = output / "B_brutalist_dill_pickles.png"
    assert "overwriting B_brutalist_dill_pickles.png" in captured
    assert published.read_bytes() == second.read_bytes()


def test_download_reads_only_one_byte_beyond_limit(monkeypatch):
    response = Response(b"x" * 100)
    monkeypatch.setattr("lith.imagebytes.DOWNLOAD_MAX_BYTES", 10)
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_kw: response)
    with pytest.raises(ValueError, match="exceeds"):
        fetch_image("https://provider.example/no-newlines")
    assert response.body.tell() == 11


def test_png_expansion_is_bounded(monkeypatch):
    monkeypatch.setattr("lith.imagebytes.PNG_MAX_DECOMPRESSED_BYTES", 100)
    assert looks_like_image(png(1, 1))
    assert not looks_like_image(png(100, 100))


def test_png_rejects_truncated_and_trailing_zlib_data():
    header = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    data = zlib.compress(b"\x00\x20\x80\x40")
    for invalid in (data[:-1], data + b"garbage", data + data):
        body = b"\x89PNG\r\n\x1a\n" + header + _chunk(b"IDAT", invalid) + _chunk(b"IEND", b"")
        assert not looks_like_image(body)
    # IDAT boundaries need not align with compressed blocks.
    body = b"\x89PNG\r\n\x1a\n" + header
    body += b"".join(_chunk(b"IDAT", bytes([value])) for value in data)
    assert looks_like_image(body + _chunk(b"IEND", b""))


@pytest.mark.parametrize("tail", [b"x", b"JUNK" + struct.pack("<I", 100) + b"x"])
def test_webp_rejects_malformed_tail_after_valid_frame(tail):
    body = WEBP_1X1 + tail
    body = body[:4] + struct.pack("<I", len(body) - 8) + body[8:]
    assert not looks_like_image(body)
    assert image_size(body) is None


def test_atomic_write_failure_preserves_existing_artifact(tmp_path, monkeypatch):
    from lith.imagebytes import write_atomic

    target = tmp_path / "image.png"
    target.write_bytes(b"previous")

    def fail_replace(self, destination):
        assert self.read_bytes() == b"replacement"
        assert destination.read_bytes() == b"previous"
        raise OSError("rename failed")

    monkeypatch.setattr(pathlib.Path, "replace", fail_replace)
    with pytest.raises(OSError, match="rename failed"):
        write_atomic(target, b"replacement")
    assert target.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [target]


def test_overlapping_atomic_writes_use_private_staging(tmp_path, monkeypatch):
    from lith.imagebytes import write_atomic

    target = tmp_path / "image.png"
    replace = pathlib.Path.replace
    stages = []

    def overlap(self, destination):
        stages.append(self)
        if len(stages) == 1:
            write_atomic(destination, b"second writer")
            assert destination.read_bytes() == b"second writer"
            assert self.read_bytes() == b"first writer"
        return replace(self, destination)

    monkeypatch.setattr(pathlib.Path, "replace", overlap)
    write_atomic(target, b"first writer")
    assert len(set(stages)) == 2
    assert target.read_bytes() == b"first writer"
    assert list(tmp_path.iterdir()) == [target]


def test_png_stream_accepts_large_valid_output():
    assert looks_like_image(png(1024, 1024))


def test_atomic_write_failure_cleans_up_partial_data(tmp_path, monkeypatch):
    from lith import imagebytes

    target = tmp_path / "image.png"
    target.write_bytes(b"previous")
    create = imagebytes.tempfile.NamedTemporaryFile

    class FailingFile:
        def __enter__(self):
            self.stream = create(dir=tmp_path, suffix=".part", delete=False)
            self.name = self.stream.name
            return self

        def write(self, body):
            self.stream.write(body[:2])
            raise OSError("disk full")

        def __exit__(self, *_args):
            self.stream.close()

    monkeypatch.setattr(imagebytes.tempfile, "NamedTemporaryFile", lambda **_kwargs: FailingFile())
    with pytest.raises(OSError, match="disk full"):
        imagebytes.write_atomic(target, b"replacement")
    assert target.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [target]
