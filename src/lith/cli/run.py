#!/usr/bin/env python3
"""End-to-end driver for the tech-image pipeline.

The operator or Hermes supplies a generated image via ``--image-url`` or
``--image-file``. Without either source, the command prints its plan and exits.
"""

from __future__ import annotations

import argparse
import pathlib
import struct
import sys
import urllib.parse
import urllib.request

from lith import load_recipe, output_path, render_prompt
from lith.paths import default_output_dir
from lith.styles import get_family, load_styles

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


def aspect_mismatch(body: bytes, requested: str, tolerance: float = 0.02) -> str | None:
    """Describe how the delivered frame differs from the one the recipe asked for.

    The model is free to ignore ``aspect_ratio`` — grok-imagine has no 4:5 and
    silently substitutes another ratio. That matters because the layout the
    prompt describes was composed for the requested frame, so the substitution
    has to be visible rather than discovered later in the image.
    """
    size = _image_size(body)
    if size is None or ":" not in requested:
        return None
    try:
        num, den = (float(part) for part in requested.split(":", 1))
    except ValueError:
        return None
    if not den or not num:
        return None
    width, height = size
    if not height:
        return None
    want, got = num / den, width / height
    if abs(got - want) <= tolerance * want:
        return None
    return f"requested {requested} ({want:.3f}), received {width}x{height} ({got:.3f})"


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


def load_local(src: pathlib.Path, dst: pathlib.Path) -> pathlib.Path:
    """Copy a recognized local image into the pipeline's raw-image path."""
    if not src.is_file():
        raise FileNotFoundError(f"input not found: {src}")
    body = src.read_bytes()
    if not _looks_like_image(body):
        raise ValueError(f"local file is not a recognized image format: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst.resolve():
        dst.write_bytes(body)
    return dst


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the image pipeline end-to-end.")
    parser.add_argument("--recipe", type=pathlib.Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        help="Directory for the published file. Defaults beside the recipe.",
    )
    image_source = parser.add_mutually_exclusive_group()
    image_source.add_argument(
        "--image-url", help="Raw generated image URL (from image_generate)"
    )
    image_source.add_argument(
        "--image-file", type=pathlib.Path, help="Local raw generated image path"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when the delivered frame does not match the request. "
        "The file is still published, since the bytes are the evidence.",
    )
    args = parser.parse_args()

    recipe = load_recipe(args.recipe)
    output_dir = args.output_dir or default_output_dir(args.recipe)
    styles = load_styles()
    style = get_family(styles, recipe.style)
    rendered = render_prompt(style, recipe.brief, model=recipe.model)
    # Extension is unknown until the bytes arrive: grok returns JPEG,
    # gpt-image-1 returns PNG. Name the artifact after what actually lands.
    stem = output_path(output_dir, recipe.family_key, recipe.brief["headline"], "")

    if not args.image_url and not args.image_file:
        print(f"[recipe]      {args.recipe}", flush=True)
        print(f"[family]      {recipe.family_key}", flush=True)
        print(f"[style]       {rendered['style']}", flush=True)
        print(f"[aspect]      {rendered['aspect_ratio']}", flush=True)
        for note in (rendered["aspect_note"], rendered["copy_note"]):
            if note:
                print(f"[warn]        {note}", flush=True)
        print(f"[model]       {recipe.model} (n={recipe.n})", flush=True)
        print("[prompt]", flush=True)
        for line in rendered["prompt"].splitlines():
            print(f"  {line}", flush=True)
        print(f"[output]      {stem}.<jpg|png|webp>", flush=True)
        print(
            "Next: call image_generate with the prompt, then re-run with "
            "--image-url or --image-file.",
            flush=True,
        )
        return 0

    staged = stem.with_suffix(".part")
    if args.image_url:
        print(f"[download]    {args.image_url}", flush=True)
        download(args.image_url, staged)
    else:
        print(f"[copy]        {args.image_file}", flush=True)
        load_local(args.image_file, staged)

    body = staged.read_bytes()
    drift = aspect_mismatch(body, rendered["aspect_ratio"])
    if drift:
        print(f"[warn]        aspect: {drift}", flush=True)
    completed = stem.with_suffix(_image_ext(body[:12]))
    # Output paths key on family and headline only, so a sweep whose recipes
    # share a headline silently collapses onto one file per family.
    if completed.exists():
        print(f"[warn]        overwriting {completed.name}", flush=True)
    staged.replace(completed)
    print(f"[done]        {completed}", flush=True)
    # A warning on stdout is invisible to a sweep script scraping exit codes,
    # which is how 18 reframed images once published as a clean run.
    if drift and args.strict:
        print("[fail]        strict: delivered frame does not match", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
