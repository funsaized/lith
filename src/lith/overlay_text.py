#!/usr/bin/env python3
"""Deterministic typography overlay for generated tech images.

The image model is responsible for visual layout. This script owns literal
copy so the final artifact never ships hallucinated body text.

Example:
    python overlay_text.py \
      --input outputs/raw.jpg \
      --output outputs/final.png \
      --line SYSTEM='32 language runtimes online' \
      --line NEW='Full-stack · AI · MLOps' \
      --line READY='One agent. Every stack.'
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

DEFAULT_FONT = pathlib.Path("/System/Library/Fonts/Menlo.ttc")


def parse_line(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("line must be LABEL=copy")
    label, copy = value.split("=", 1)
    label = label.strip()
    copy = copy.strip()
    if not label or not copy:
        raise argparse.ArgumentTypeError("label and copy must both be non-empty")
    return label, copy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--line", action="append", type=parse_line, required=True)
    parser.add_argument("--font", type=pathlib.Path, default=DEFAULT_FONT)
    parser.add_argument("--point-size", type=int, default=25)
    parser.add_argument("--x", type=int, default=150)
    parser.add_argument("--y", type=int, default=405)
    parser.add_argument("--line-height", type=int, default=40)
    parser.add_argument("--body-x", type=int, default=295)
    parser.add_argument("--label-color", default="#FF3030")
    parser.add_argument("--body-color", default="#00E5FF")
    parser.add_argument("--mask", default="120,365 1165,515", help="x1,y1 x2,y2")
    args = parser.parse_args()

    magick = shutil.which("magick")
    if not magick:
        print("error: ImageMagick 'magick' executable not found", file=sys.stderr)
        return 2
    if not args.input.is_file():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2
    if not args.font.is_file():
        print(f"error: font not found: {args.font}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        magick,
        str(args.input),
        "-fill", "#000000",
        "-draw", f"rectangle {args.mask}",
        "-font", str(args.font),
        "-pointsize", str(args.point_size),
    ]

    for index, (label, copy) in enumerate(args.line):
        y = args.y + index * args.line_height
        label_text = f"[{label}]"
        cmd += [
            "-fill", args.label_color,
            "-annotate", f"+{args.x}+{y}", label_text,
            "-fill", args.body_color,
            "-annotate", f"+{args.body_x}+{y}", copy,
        ]

    cmd.append(str(args.output))
    subprocess.run(cmd, check=True)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
