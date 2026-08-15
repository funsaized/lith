"""End-to-end smoke test against the existing reference artifact."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "outputs" / "B_brutalist_32_langs_raw.jpg"
REFERENCE = REPO / "outputs" / "B_brutalist_32_langs_verified.png"
TOLERANCE_PIXELS = 200


@pytest.mark.skipif(not shutil.which("magick"), reason="ImageMagick not installed")
@pytest.mark.skipif(
    not RAW.exists() or not REFERENCE.exists(), reason="reference artifacts missing"
)
def test_driver_reproduces_reference_within_tolerance(tmp_path):
    out_dir = tmp_path / "smoke"
    out_dir.mkdir()
    final_png = out_dir / "B_brutalist_32_langs.png"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lith.cli.run",
            "--recipe",
            str(REPO / "recipes" / "live_test_recipe.json"),
            "--image-file",
            str(RAW),
            "--line",
            "SYSTEM=32 language runtimes online",
            "--line",
            "NEW=Full-stack · AI · MLOps",
            "--line",
            "READY=One agent. Every stack.",
            "--output-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"driver failed: {result.stderr}"
    assert final_png.exists(), f"expected {final_png} to exist"
    assert final_png.stat().st_size > 0
    assert result.stdout.index("[copy]") < result.stdout.index(str(final_png)), (
        f"driver log order is misleading under capture: {result.stdout}"
    )

    comparison = subprocess.run(
        [
            "magick",
            "compare",
            "-metric",
            "AE",
            "-fuzz",
            "1%",
            str(REFERENCE),
            str(final_png),
            str(tmp_path / "diff.png"),
        ],
        capture_output=True,
        text=True,
    )
    output = (comparison.stderr or "") + (comparison.stdout or "")
    first_token = output.strip().split()[0] if output.strip() else ""
    assert first_token, f"magick compare returned no metric: {comparison}"
    diff_pixels = int(float(first_token))
    assert diff_pixels <= TOLERANCE_PIXELS, (
        f"pixel diff {diff_pixels} exceeds tolerance {TOLERANCE_PIXELS} "
        "(floor=0; smallest measured regression=870)"
    )
