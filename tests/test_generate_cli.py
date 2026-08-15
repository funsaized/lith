import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_pure_mode_prints_rendered_prompt():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "generate.py"),
         "--topic", "t", "--style", "B", "--headline", "32 LANGS", "--icon", "globe"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "Headline='32 LANGS'" in out or "Headline: '32 LANGS'" in out
    assert "pure black" in out


def test_call_mode_emits_json_envelope():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "generate.py"),
         "--topic", "t", "--style", "B", "--headline", "32 LANGS", "--icon", "globe",
         "--call", "--emit-json"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    env = json.loads(result.stdout)
    for key in ("prompt", "negative_prompt", "aspect_ratio", "model", "n",
                "seed", "output_path", "style"):
        assert key in env, f"envelope missing key: {key}"


def test_filename_includes_full_family_key_in_flag_mode():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "generate.py"),
         "--topic", "t", "--style", "B", "--headline", "32 LANGS", "--icon", "globe",
         "--call", "--emit-json"],
        capture_output=True, text=True,
    )
    env = json.loads(result.stdout)
    assert env["output_path"].endswith("B_brutalist_32_langs.png"), env["output_path"]
    assert "_x_" not in env["output_path"]


def test_filename_slugifies_for_path_separators():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "generate.py"),
         "--topic", "t", "--style", "B", "--headline", "AI/ML: v2", "--icon", "gear"],
        capture_output=True, text=True,
    )
    out = result.stdout + result.stderr
    assert "B_brutalist_ai_ml_v2.png" in out or "B_brutalist_ai_ml_v2" in out
