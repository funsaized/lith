import json
import subprocess
import sys


def test_pure_mode_prints_rendered_prompt():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lith.cli.generate",
            "--topic",
            "t",
            "--style",
            "B",
            "--headline",
            "32 LANGS",
            "--icon",
            "globe",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    out = result.stdout + result.stderr
    # The headline reaches the prompt through the spec's TITLE line, which is
    # the single copy path every family now shares.
    assert "TITLE: 32 LANGS" in out
    assert "pure-black panel" in out


def test_call_mode_emits_json_envelope():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lith.cli.generate",
            "--topic",
            "t",
            "--style",
            "B",
            "--headline",
            "32 LANGS",
            "--icon",
            "globe",
            "--call",
            "--emit-json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    env = json.loads(result.stdout)
    for key in (
        "prompt",
        "negative_prompt",
        "aspect_ratio",
        "model",
        "n",
        "seed",
        "output_path",
        "style",
    ):
        assert key in env, f"envelope missing key: {key}"


def test_filename_includes_full_family_key_in_flag_mode():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lith.cli.generate",
            "--topic",
            "t",
            "--style",
            "B",
            "--headline",
            "32 LANGS",
            "--icon",
            "globe",
            "--call",
            "--emit-json",
        ],
        capture_output=True,
        text=True,
    )
    env = json.loads(result.stdout)
    # Stem only — the extension is lith-run's to choose from the image bytes.
    assert env["output_path"].endswith("B_brutalist_32_langs"), env["output_path"]
    assert "_x_" not in env["output_path"]


def test_filename_slugifies_for_path_separators():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lith.cli.generate",
            "--topic",
            "t",
            "--style",
            "B",
            "--headline",
            "AI/ML: v2",
            "--icon",
            "gear",
        ],
        capture_output=True,
        text=True,
    )
    out = result.stdout + result.stderr
    assert "B_brutalist_ai_ml_v2.png" in out or "B_brutalist_ai_ml_v2" in out


def test_generate_and_run_agree_on_the_output_path():
    """A derived path is a stem in both CLIs: neither has the bytes that name it."""
    import subprocess, sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    recipe = str(repo / "recipes" / "live_test_recipe.json")

    def out_line(module):
        r = subprocess.run(
            [sys.executable, "-m", module, "--recipe", recipe],
            capture_output=True, text=True, cwd=repo,
        )
        assert r.returncode == 0, r.stderr
        return next(l for l in r.stdout.splitlines() if l.startswith("[output]"))

    assert out_line("lith.cli.generate") == out_line("lith.cli.run")
    assert ".png" not in out_line("lith.cli.generate")


def test_generate_honors_an_explicit_out_verbatim(tmp_path):
    import subprocess, sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    target = tmp_path / "chosen.png"
    r = subprocess.run(
        [sys.executable, "-m", "lith.cli.generate", "--recipe",
         str(repo / "recipes" / "live_test_recipe.json"), "--out", str(target)],
        capture_output=True, text=True, cwd=repo,
    )
    assert r.returncode == 0, r.stderr
    assert f"[output]      {target}" in r.stdout


def test_envelope_carries_the_aspect_note():
    """An agent reads the envelope, not stderr — a clamp must be machine-visible."""
    import json, subprocess, sys

    r = subprocess.run(
        [sys.executable, "-m", "lith.cli.generate", "--topic", "t", "--style", "B",
         "--headline", "X", "--model", "gpt-image-1", "--call", "--emit-json"],
        capture_output=True, text=True,
    )
    env = json.loads(r.stdout)
    assert env["aspect_ratio"] == "3:2"
    assert "cannot produce 16:9" in env["aspect_note"]
    assert "warning:" in r.stderr

    clean = subprocess.run(
        [sys.executable, "-m", "lith.cli.generate", "--topic", "t", "--style", "B",
         "--headline", "X", "--call", "--emit-json"],
        capture_output=True, text=True,
    )
    assert json.loads(clean.stdout)["aspect_note"] is None
