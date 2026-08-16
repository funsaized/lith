"""End-to-end smoke test: the driver publishes the model's image untouched."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "outputs" / "B_brutalist_32_langs_raw.jpg"
pytestmark = pytest.mark.integration


@pytest.mark.skipif(not RAW.exists(), reason="reference artifact missing")
def test_driver_publishes_model_image_under_recipe_name(tmp_path):
    out_dir = tmp_path / "smoke"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lith.cli.run",
            "--recipe",
            str(REPO / "recipes" / "live_test_recipe.json"),
            "--image-file",
            str(RAW),
            "--output-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"driver failed: {result.stderr}"

    # Extension follows the bytes, not the recipe: this fixture is a JPEG.
    final = out_dir / "B_brutalist_dill_pickles.jpg"
    assert final.exists(), f"expected {final}, got {list(out_dir.iterdir())}"
    assert final.read_bytes() == RAW.read_bytes(), "driver must not re-encode"
    assert not list(out_dir.glob("*.part")), "staging file left behind"
    assert result.stdout.index("[copy]") < result.stdout.index(str(final)), (
        f"driver log order is misleading under capture: {result.stdout}"
    )
