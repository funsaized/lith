#!/usr/bin/env python3
"""Render a brief into a prompt and image-generation plan.

Pure CLI mode (default) prints the rendered prompt and exits. ``--call``
emits a call envelope for a Hermes session or operator; pair it with
``--emit-json`` for machine-readable output.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from lith import load_recipe, output_path, render_prompt
from lith.aspect import request_limit_notes
from lith.paths import default_output_dir
from lith.recipe import FAMILY_KEYS
from lith.styles import get_family, load_styles


def build_brief(args: argparse.Namespace) -> dict:
    return {
        "topic": args.topic,
        "headline": args.headline,
        "icon": args.icon,
        "aspect": args.aspect,
        "volume": "1",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a brief into a prompt.")
    parser.add_argument("--recipe", type=pathlib.Path)
    parser.add_argument("--topic")
    parser.add_argument("--style", choices=list("ABCDEFG"))
    parser.add_argument(
        "--aspect",
        choices=[
            "1:1",
            "3:4",
            "4:3",
            "9:16",
            "16:9",
            "2:3",
            "3:2",
            "9:19.5",
            "19.5:9",
            "9:20",
            "20:9",
            "1:2",
            "2:1",
            "auto",
            "21:9",
        ],
    )
    parser.add_argument("--headline")
    parser.add_argument("--icon", default="gear")
    parser.add_argument("--n", type=int, default=4)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--model",
        default="grok-imagine-image-2.0",
        choices=[
            "grok-imagine-image-2.0",
            "gpt-image-2",
            "gpt-image-2-2026-04-21",
            "gpt-image-1.5",
            "gpt-image-1",
            "gpt-image-1-mini",
            "image-01",
        ],
    )
    parser.add_argument("--out", type=pathlib.Path)
    parser.add_argument(
        "--call", action="store_true", help="Emit call envelope instead of just printing"
    )
    parser.add_argument(
        "--emit-json", action="store_true", help="With --call, emit machine-readable JSON"
    )
    args = parser.parse_args()

    styles = load_styles()
    # Anchored to the recipe when there is one; an agent's cwd is arbitrary.
    output_dir = (
        default_output_dir(args.recipe)
        if args.recipe
        else pathlib.Path.cwd() / "outputs"
    )

    if args.recipe:
        recipe = load_recipe(args.recipe)
        style = get_family(styles, recipe.style)
        brief = recipe.brief
        n = recipe.n
        model = recipe.model
        out = args.out or output_path(
            output_dir, recipe.family_key, brief["headline"], ""
        )
    else:
        for required in ("topic", "style", "headline"):
            if not getattr(args, required):
                parser.error(f"--{required} required when --recipe not used")
        style = get_family(styles, args.style)
        brief = build_brief(args)
        n = args.n
        model = args.model
        out = args.out or output_path(
            output_dir, FAMILY_KEYS[args.style], brief["headline"], ""
        )

    rendered = render_prompt(style, brief, model=model)
    limit_notes = request_limit_notes(model, n, rendered["prompt"])
    for note in (rendered["aspect_note"], rendered["copy_note"], *limit_notes):
        if note:
            print(f"warning: {note}", file=sys.stderr, flush=True)

    if args.call:
        envelope = {
            "prompt": rendered["prompt"],
            "negative_prompt": rendered["negative_prompt"],
            "aspect_ratio": rendered["aspect_ratio"],
            "model": model,
            "n": n,
            "seed": args.seed,
            "output_path": str(out),
            "style": rendered["style"],
            # Machine-visible too: an agent consuming the envelope should not
            # have to read stderr to learn the ratio was substituted.
            "aspect_note": rendered["aspect_note"],
            "copy_note": rendered["copy_note"],
            "limit_notes": limit_notes,
        }
        if args.emit_json:
            print(json.dumps(envelope, indent=2))
        else:
            for key, value in envelope.items():
                print(f"{key}={value}")
        return 0

    print(f"[brief]       {brief}")
    print(f"[style]       {rendered['style']}")
    print(f"[aspect]      {rendered['aspect_ratio']}")
    print("[prompt]")
    for line in rendered["prompt"].splitlines():
        print(f"  {line}")
    print(f"[negative]    {rendered['negative_prompt']}")
    print(f"[plan]        {n} candidates via {model}, seed={args.seed}")
    # A derived path is a stem: only lith-run sees the bytes that name it.
    print(f"[output]      {out}" + ("" if args.out else ".<jpg|png|webp>"))
    print("Next: pass --call to emit the envelope for image_generate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
