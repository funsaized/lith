import pathlib
import subprocess
import sys

# Delegate to scripts/overlay_text.py. Do not reimplement the ImageMagick
# argv here: that script owns the dimension-specific tuning constants.
_OVERLAY_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "overlay_text.py"


def overlay_typography(
    src: pathlib.Path,
    dst: pathlib.Path,
    lines: list[tuple[str, str]],
    font: pathlib.Path | None = None,
) -> pathlib.Path:
    """Overlay literal copy using the project's ImageMagick script."""
    if not _OVERLAY_SCRIPT.is_file():
        raise FileNotFoundError(f"overlay_text.py not found: {_OVERLAY_SCRIPT}")
    if not src.is_file():
        raise FileNotFoundError(f"input not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(_OVERLAY_SCRIPT),
        "--input",
        str(src),
        "--output",
        str(dst),
    ]
    if font is not None:
        cmd += ["--font", str(font)]
    for label, body in lines:
        cmd += ["--line", f"{label}={body}"]

    subprocess.run(cmd, check=True)
    return dst
