#!/usr/bin/env python3
"""End-to-end driver for the tech-image pipeline.

The operator or Hermes supplies a generated image via ``--image-url`` or
``--image-file``. Without either source, the command prints its plan and exits.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.pipeline.paths import output_path
from scripts.pipeline.recipe import load_recipe
from scripts.pipeline.render import render_prompt
from scripts.pipeline.styles import get_family, load_styles
from scripts.pipeline.typography import overlay_typography

STYLES_PATH = ROOT / "templates" / "styles.json"
ALLOWED_SCHEMES = ("http", "https")
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_MAX_BYTES = 25 * 1024 * 1024
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _looks_like_image(body: bytes) -> bool:
    return (
        body.startswith(JPEG_MAGIC)
        or body.startswith(PNG_MAGIC)
        or (body.startswith(b"RIFF") and body[8:12] == b"WEBP")
    )


def parse_line(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("line must be LABEL=copy")
    label, copy = value.split("=", 1)
    label = label.strip()
    copy = copy.strip()
    if not label or not copy:
        raise argparse.ArgumentTypeError("label and copy must both be non-empty")
    return label, copy


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

    req = urllib.request.Request(
        url, headers={"User-Agent": "lith/1.0"}
    )
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
    parser.add_argument("--output-dir", type=pathlib.Path, default=ROOT / "outputs")
    image_source = parser.add_mutually_exclusive_group()
    image_source.add_argument(
        "--image-url", help="Raw generated image URL (from image_generate)"
    )
    image_source.add_argument(
        "--image-file", type=pathlib.Path, help="Local raw generated image path"
    )
    parser.add_argument("--font", type=pathlib.Path)
    parser.add_argument(
        "--line",
        type=parse_line,
        action="append",
        default=[],
        help="LABEL=copy line to overlay. Pass multiple times.",
    )
    args = parser.parse_args()

    recipe = load_recipe(args.recipe)
    styles = load_styles(STYLES_PATH)
    style = get_family(styles, recipe.style)
    rendered = render_prompt(style, recipe.brief)
    out_final = output_path(
        args.output_dir, recipe.family_key, recipe.brief["headline"], ".png"
    )

    if not args.image_url and not args.image_file:
        print(f"[recipe]      {args.recipe}", flush=True)
        print(f"[family]      {recipe.family_key}", flush=True)
        print(f"[style]       {rendered['style']}", flush=True)
        print(f"[aspect]      {rendered['aspect_ratio']}", flush=True)
        print(f"[model]       {recipe.model} (n={recipe.n})", flush=True)
        print("[prompt]", flush=True)
        for line in rendered["prompt"].splitlines():
            print(f"  {line}", flush=True)
        print(f"[output]      {out_final}", flush=True)
        print(
            "Next: call image_generate with the prompt, then re-run with "
            "--image-url or --image-file.",
            flush=True,
        )
        return 0

    raw = output_path(
        args.output_dir, recipe.family_key, recipe.brief["headline"], "_raw.jpg"
    )

    if args.image_url:
        print(f"[download]    {args.image_url} -> {raw}", flush=True)
        download(args.image_url, raw)
    else:
        print(f"[copy]        {args.image_file} -> {raw}", flush=True)
        load_local(args.image_file, raw)

    if not args.line:
        print(
            "[warn]        no --line supplied; writing raw only (no overlay)",
            flush=True,
        )
        completed = raw
    else:
        overlay_kwargs = {"font": args.font} if args.font else {}
        overlay_typography(raw, out_final, lines=args.line, **overlay_kwargs)
        completed = out_final

    print(f"[done]        {completed}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
