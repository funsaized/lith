#!/usr/bin/env python3
"""Validate a generated image and publish it as the finished print.

The operator or Hermes supplies a generated image via ``--image-url`` or
``--image-file``. Without either source, the command prints its plan and exits.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from lith import load_recipe, output_path, render_prompt
from lith.imagebytes import fetch_image, image_ext, image_size, looks_like_image, write_atomic
from lith.paths import default_output_dir
from lith.styles import get_family, load_styles


def aspect_mismatch(body: bytes, requested: str, tolerance: float = 0.02) -> str | None:
    """Describe how the delivered frame differs from the one the recipe asked for.

    The model is free to ignore ``aspect_ratio`` — grok-imagine has no 4:5 and
    silently substitutes another ratio. That matters because the layout the
    prompt describes was composed for the requested frame, so the substitution
    has to be visible rather than discovered later in the image.
    """
    size = image_size(body)
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


def load_local(src: pathlib.Path, dst: pathlib.Path) -> pathlib.Path:
    """Copy a recognized local image into the pipeline's raw-image path."""
    body = _local_bytes(src)
    if src.resolve() != dst.resolve():
        write_atomic(dst, body)
    return dst


def _local_bytes(src: pathlib.Path) -> bytes:
    if not src.is_file():
        raise FileNotFoundError(f"input not found: {src}")
    body = src.read_bytes()
    if not looks_like_image(body):
        raise ValueError(f"local file is not a recognized image format: {src}")
    return body


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

    if args.image_url:
        print(f"[download]    {args.image_url}", flush=True)
        body = fetch_image(args.image_url)
    else:
        print(f"[copy]        {args.image_file}", flush=True)
        body = _local_bytes(args.image_file)

    drift = aspect_mismatch(body, rendered["aspect_ratio"])
    if drift:
        print(f"[warn]        aspect: {drift}", flush=True)
    completed = stem.with_suffix(image_ext(body[:12]))
    # Output paths key on family and headline only, so a sweep whose recipes
    # share a headline silently collapses onto one file per family.
    if completed.exists():
        print(f"[warn]        overwriting {completed.name}", flush=True)
    write_atomic(completed, body)
    print(f"[done]        {completed}", flush=True)
    # A warning on stdout is invisible to a sweep script scraping exit codes,
    # which is how 18 reframed images once published as a clean run.
    if drift and args.strict:
        print("[fail]        strict: delivered frame does not match", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
