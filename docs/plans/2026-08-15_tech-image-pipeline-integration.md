# Tech-Image Pipeline Hermes Integration

> **For Codex:** Implement task-by-task. Each task is independently committable. Don't bundle tasks. Tests are invariants, not theater — every test asserts something the implementation could plausibly get wrong.

**Goal:** Make the Python scaffolding (prompt render, recipe loading, file paths, ImageMagick typography overlay) the deterministic spine of an end-to-end image generation pipeline, with Hermes supplying the model-bound work (LLM topic expansion, image generation).

**Architecture:** Three-layer split.
- **Library layer** (`scripts/pipeline/`) — pure Python: prompt rendering, recipe loading, file-path helpers, subprocess invocations. Importable. No Hermes calls.
- **Driver layer** (`scripts/run.py`) — thin CLI that wires library calls together and accepts the model-generated image via `--image-url` (remote) or `--image-file` (local) from the operator or a Hermes session.
- **Skill layer** (`skills/tech-image-pipeline/SKILL.md`) — tells any future Hermes session how to use this project.

**Out of scope for v1:** Video augmentation, multi-candidate scoring, calendar rotation, aspect-aware overlay masks. Documented in §9 roadmap; future plan tasks.

**Tech Stack:** Python 3.11+ stdlib (argparse, json, pathlib, subprocess, dataclasses, urllib, re), ImageMagick 7 (`magick` at `/opt/homebrew/bin/magick`), pytest (added in Task 0).

---

## Current State

- `templates/styles.json` — seven style families (A–G). **Bug: C_patent is missing the `{headline}` slot** in its `prompt_template`. All other six families have it. Fixed in Task 1.
- `recipes/live_test_recipe.json` — single recipe: family B, "32 LANGS". **Real.**
- `scripts/generate.py` — renders prompt + dry-run plan. **Stub for actual generation.**
- `scripts/overlay_text.py` — ImageMagick-driven, draws literal copy. **Real and working.**
- `outputs/B_brutalist_32_langs_*.{jpg,png}` — three files: `_raw.jpg` (model output), `_verified.png` (canonical overlay result, bit-for-bit reproducible from `_raw.jpg` with `overlay_text.py` defaults), and `_final.png` (a 2121-pixel stale duplicate of an earlier overlay run). `_verified.png` is the reference artifact; `_final.png` should be deleted during Task 0 cleanup.
- `skills/` — empty placeholder.
- `README.md` — design doc; §7 over-promises what the script does today.
- **No pytest installed.** Confirmed: `python3 -m pytest` → No module named pytest. Fixed in Task 0.

---

## Task 0: Bootstrap (pytest + git)

**Objective:** Get the prerequisites in place so Task 1's tests can actually run and every subsequent task can commit. No application code yet.

**Files:**
- Create: `requirements-dev.txt`
- Create: `.gitignore`

**Step 1: Install pytest**

macOS system python's pip is restricted. Use a project venv, not system pip.

```bash
cd /Users/saiguy/Documents/programming/funsaized/tech-image-pipeline
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest --version
```

Expected: `pytest X.Y.Z` prints successfully.

If `python3 -m venv` fails on the system python (it does on some macOS), fall back to:

```bash
python3 -m pip install --user pytest
~/.local/bin/pytest --version
```

Document which path worked in the commit message.

**Step 2: Write `requirements-dev.txt`**

```
pytest>=8.0
```

**Step 3: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.DS_Store
```

**Step 4: Initialize git (if not already)**

```bash
# Delete the stale _final.png — _verified.png is the canonical reference.
rm -f outputs/B_brutalist_32_langs_final.png
git init
git add requirements-dev.txt .gitignore
git commit -m "chore: bootstrap project with pytest and gitignore"
```

Verify with `git log --oneline` — should show one commit.

---

## Task 1: Create library skeleton + fix C_patent template

**Objective:** Establish the importable library surface. Fix the missing `{headline}` slot in `C_patent`. Preserve original `_palette_value` behavior (lists joined with `" | "`).

**Files:**
- Create: `scripts/pipeline/__init__.py` (empty)
- Create: `scripts/pipeline/render.py`
- Create: `scripts/pipeline/recipe.py`
- Create: `scripts/pipeline/paths.py`
- Create: `scripts/pipeline/styles.py`
- Modify: `templates/styles.json` (add `{headline}` slot to `C_patent.prompt_template`)
- Test: `tests/test_pipeline.py`

**Step 1: Fix C_patent template**

In `templates/styles.json`, the `C_patent.prompt_template` currently has slots `{icon}` and `{volume}` only — no `{headline}`. Replace with:

```
"Sepia paper background (#E8DCC4), fine ink-line drawing in #1A1A1A. Centered technical illustration of a {icon}. Border: thin double-rule with ornate corner ornaments (fleurons, sunbursts). Blue or red ink highlights for arrows, measurements, callouts. Top: small all-caps 'TECHNICAL MANUAL — VOLUME {volume}' in serif (Times, Caslon) with the headline '{headline}' below it in a slightly larger serif. Bottom: 2-3 numbered callouts in the same serif pointing into the diagram with thin lines. Patent-style 'FIG. 1' labels. Aged feel — slight grain, vignette, light tea-stain discoloration near corners. Mood: NASA 1962, an Edwardian engineer's notebook."
```

**Step 2: Write tests**

```python
# tests/test_pipeline.py
import json
from pathlib import Path

import pytest

from scripts.pipeline.paths import output_path, slug
from scripts.pipeline.recipe import FAMILY_KEYS, load_recipe
from scripts.pipeline.render import render_prompt
from scripts.pipeline.styles import load_styles, get_family

STYLES_PATH = Path(__file__).resolve().parents[1] / "templates" / "styles.json"


def test_slug_lowercases_and_strips_non_alnum():
    assert slug("32 LANGS") == "32_langs"
    assert slug("AI/ML: v2") == "ai_ml_v2"   # regression: was producing a slash
    assert slug("  ") == "untitled"


def test_output_path_uses_slug(tmp_path):
    p = output_path(tmp_path, "B_brutalist", "32 LANGS", ".png")
    assert p == tmp_path / "B_brutalist_32_langs.png"


def test_load_recipe_validates_required_fields(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({
        "name": "x", "style": "B",
        "brief": {"topic": "t", "headline": "h", "icon": "i", "aspect": "16:9"},
        "model": "grok-imagine-image-quality",
    }))
    r = load_recipe(p)
    assert r.name == "x"
    assert r.family_key == "B_brutalist"


def test_load_recipe_rejects_missing_brief_fields(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"name": "x", "style": "B", "brief": {"topic": "t"}}))
    with pytest.raises(ValueError, match="missing brief fields"):
        load_recipe(p)


def test_render_prompt_substitutes_fields():
    style = {
        "prompt_template": "Headline={headline} icon={icon} bg={base_color} accent={accent}",
        "negative_prompt": "pastel",
        "palette": {"accent": "#00E5FF", "background": "#000000"},
        "name": "Test", "default_aspect": "16:9",
    }
    out = render_prompt(style, {"headline": "32 LANGS", "icon": "globe", "aspect": "16:9"})
    assert out["prompt"].startswith("Headline=32 LANGS")
    assert "bg=#000000" in out["prompt"]
    assert out["aspect_ratio"] == "16:9"


def test_palette_value_joins_lists_with_pipe():
    """Regression: A_sticker has a list of accent colors. The original
    generate.py joined with ' | '. render.py must preserve that — picking
    field[0] silently changes the prompt for A_sticker only."""
    style = {
        "prompt_template": "palette: {accent}",
        "palette": {"accent": ["#FF2E88", "#00E5FF", "#F2FF00", "#FF6B35"]},
        "name": "X", "default_aspect": "16:9",
    }
    out = render_prompt(style, {"headline": "X", "icon": "i", "aspect": "16:9"})
    assert "FF2E88 | #00E5FF | #F2FF00 | #FF6B35" in out["prompt"]


def test_all_seven_families_have_headline_slot():
    """Regression for C_patent: every family template must accept {headline}.
    A single missing slot means the headline vanishes from that family."""
    styles = load_styles(STYLES_PATH)
    for letter in "ABCDEFG":
        fam = get_family(styles, letter)
        out = render_prompt(fam, {
            "topic": "t", "headline": "TEST_HEADLINE", "icon": "gear", "aspect": "16:9",
        })
        assert "{headline}" not in out["prompt"], (
            f"family {letter} left an unfilled {{headline}} placeholder: {out['prompt'][:200]}"
        )
        assert "TEST_HEADLINE" in out["prompt"], (
            f"family {letter} dropped the headline from the rendered prompt"
        )


def test_family_keys_complete():
    for letter in "ABCDEFG":
        assert letter in FAMILY_KEYS
    assert FAMILY_KEYS["B"] == "B_brutalist"
```

**Step 3: Implement library**

`scripts/pipeline/__init__.py`:
```python
# Intentionally empty. Library is importable as a namespace; consumers
# import submodules explicitly. See SKILL.md "Architecture".
```

`scripts/pipeline/paths.py`:
```python
import pathlib
import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")

def slug(text: str) -> str:
    """Lowercase, collapse non-alnum to single underscore, trim."""
    s = text.strip().lower()
    s = _SLUG_RE.sub("_", s)
    return s.strip("_") or "untitled"

def output_path(out_dir: pathlib.Path, family_key: str, headline: str, ext: str) -> pathlib.Path:
    return out_dir / f"{family_key}_{slug(headline)}{ext}"
```

`scripts/pipeline/render.py`:
```python
from typing import Any

def _palette_value(field: Any, default: str) -> str:
    """Resolve a palette field to a string suitable for prompt insertion.

    List values are joined with ' | ' — this matches the original
    generate.py behavior for A_sticker's multi-accent palette. Picking
    field[0] would silently change only A_sticker's prompt."""
    if isinstance(field, list):
        if not field:
            return default
        return " | ".join(str(x) for x in field)
    return field or default

def render_prompt(style: dict[str, Any], brief: dict[str, Any]) -> dict[str, str]:
    """Substitute brief fields into the family's prompt_template.

    Raises KeyError if the template references a slot not in the brief and
    not given a default. Intentional — silent drops are how the C_patent
    bug got into the repo."""
    palette = style.get("palette", {})
    prompt = style["prompt_template"].format(
        headline=brief.get("headline", "NEW"),
        icon=brief.get("icon", "gear"),
        base_color=_palette_value(palette.get("background"), "#000000"),
        accent=_palette_value(palette.get("accent"), "#00E5FF"),
        volume=brief.get("volume", "1"),
    )
    aspect = brief.get("aspect") or style.get("default_aspect", "16:9")
    return {
        "prompt": prompt,
        "negative_prompt": str(style.get("negative_prompt", "")),
        "aspect_ratio": str(aspect),
        "style": str(style["name"]),
    }
```

`scripts/pipeline/recipe.py`:
```python
import json
import pathlib
from dataclasses import dataclass

FAMILY_KEYS = {
    "A": "A_sticker", "B": "B_brutalist", "C": "C_patent",
    "D": "D_manga", "E": "E_screenshot", "F": "F_woodcut", "G": "G_log",
}

REQUIRED_BRIEF_KEYS = {"topic", "headline", "icon", "aspect"}

@dataclass
class Recipe:
    name: str
    style: str
    brief: dict
    model: str
    n: int
    expected_output: str | None
    description: str | None

    @property
    def family_key(self) -> str:
        return FAMILY_KEYS[self.style]

def load_recipe(path: pathlib.Path) -> Recipe:
    data = json.loads(path.read_text())
    brief = data.get("brief", {})
    missing = REQUIRED_BRIEF_KEYS - brief.keys()
    if missing:
        raise ValueError(f"recipe {path} missing brief fields: {sorted(missing)}")
    return Recipe(
        name=data.get("name", path.stem),
        style=data["style"],
        brief=brief,
        model=data.get("model", "grok-imagine-image-quality"),
        n=data.get("n", 4),
        expected_output=data.get("expected_output"),
        description=data.get("description"),
    )
```

`scripts/pipeline/styles.py`:
```python
import json
import pathlib

from scripts.pipeline.recipe import FAMILY_KEYS

def load_styles(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())

def get_family(styles: dict, letter: str) -> dict:
    return styles["families"][FAMILY_KEYS[letter]]
```

**Step 4: Run tests**

```bash
cd /Users/saiguy/Documents/programming/funsaized/tech-image-pipeline
PYTHONPATH=. .venv/bin/python -m pytest tests/test_pipeline.py -v
```

Expected: 8 passed.

**Step 5: Commit**

```bash
git add scripts/pipeline templates/styles.json tests/test_pipeline.py
git commit -m "feat(pipeline): library skeleton + fix C_patent headline slot"
```

---

## Task 2: Wire `scripts/generate.py` to the library

**Objective:** Replace inline prompt rendering with library calls. CLI surface unchanged. Add `--call --emit-json` envelope mode. Use `FAMILY_KEYS` so flag-mode filenames match recipe-mode filenames.

**Files:**
- Modify: `scripts/generate.py` (full rewrite, ~110 lines)
- Test: `tests/test_generate_cli.py`

**Step 1: Write CLI test**

```python
# tests/test_generate_cli.py
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
    for k in ("prompt", "negative_prompt", "aspect_ratio", "model", "n",
              "seed", "output_path", "style"):
        assert k in env, f"envelope missing key: {k}"


def test_filename_includes_full_family_key_in_flag_mode():
    """Regression: flag-mode used to produce 'B_x_32_langs.png' (style + '_x'),
    while recipe-mode produced 'B_brutalist_32_langs.png'. Same brief, two
    files. Family key must be the same in both modes."""
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
    """'AI/ML: v2' must not produce a slash in the filename."""
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "generate.py"),
         "--topic", "t", "--style", "B", "--headline", "AI/ML: v2", "--icon", "gear"],
        capture_output=True, text=True,
    )
    out = result.stdout + result.stderr
    # The slug must collapse the slash; no path separator should appear
    # in the output filename portion.
    assert "B_brutalist_ai_ml_v2.png" in out or "B_brutalist_ai_ml_v2" in out
```

**Step 2: Rewrite `scripts/generate.py`**

```python
#!/usr/bin/env python3
"""
generate.py — Render a brief into a prompt + plan via the pipeline library.

Pure CLI mode (default): prints the rendered prompt and exits.
--call --emit-json mode: emits a JSON envelope describing what image_generate
should be called with. Consumed by a Hermes session or the operator.

Usage:
    python scripts/generate.py --topic "..." --style B --headline "..." --icon "..."
    python scripts/generate.py --recipe recipes/live_test_recipe.json --call --emit-json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.pipeline.paths import output_path
from scripts.pipeline.recipe import FAMILY_KEYS, load_recipe
from scripts.pipeline.render import render_prompt
from scripts.pipeline.styles import get_family, load_styles

STYLES_PATH = ROOT / "templates" / "styles.json"


def build_brief(args: argparse.Namespace) -> dict:
    return {
        "topic": args.topic,
        "headline": args.headline,
        "icon": args.icon,
        "aspect": args.aspect,
        "volume": "1",
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Render a brief into a prompt.")
    p.add_argument("--recipe", type=pathlib.Path)
    p.add_argument("--topic")
    p.add_argument("--style", choices=list("ABCDEFG"))
    p.add_argument("--aspect", choices=["16:9", "4:5", "1:1", "9:16"])
    p.add_argument("--headline")
    p.add_argument("--icon", default="gear")
    p.add_argument("--n", type=int, default=4)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--model", default="grok-imagine-image-quality",
                   choices=["grok-imagine-image-quality", "grok-imagine-image",
                            "gpt-image-1", "minimax-image"])
    p.add_argument("--out", type=pathlib.Path)
    p.add_argument("--call", action="store_true",
                   help="Emit call envelope instead of just printing")
    p.add_argument("--emit-json", action="store_true",
                   help="With --call, emit machine-readable JSON")
    args = p.parse_args()

    styles = load_styles(STYLES_PATH)

    if args.recipe:
        recipe = load_recipe(args.recipe)
        style = get_family(styles, recipe.style)
        brief = recipe.brief
        n = recipe.n
        model = recipe.model
        out = args.out or output_path(ROOT / "outputs", recipe.family_key,
                                      brief["headline"], ".png")
    else:
        for required in ("topic", "style", "headline"):
            if not getattr(args, required):
                p.error(f"--{required} required when --recipe not used")
        style = get_family(styles, args.style)
        brief = build_brief(args)
        n = args.n
        model = args.model
        out = args.out or output_path(ROOT / "outputs", FAMILY_KEYS[args.style],
                                      brief["headline"], ".png")

    rendered = render_prompt(style, brief)

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
        }
        if args.emit_json:
            print(json.dumps(envelope, indent=2))
        else:
            for k, v in envelope.items():
                print(f"{k}={v}")
        return 0

    print(f"[brief]       {brief}")
    print(f"[style]       {rendered['style']}")
    print(f"[aspect]      {rendered['aspect_ratio']}")
    print("[prompt]")
    for line in rendered["prompt"].splitlines():
        print(f"  {line}")
    print(f"[negative]    {rendered['negative_prompt']}")
    print(f"[plan]        {n} candidates via {model}, seed={args.seed}")
    print(f"[output]      {out}")
    print("Next: pass --call to emit the envelope for image_generate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 3: Run tests**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_generate_cli.py -v
```

Expected: 4 passed.

**Step 4: Commit**

```bash
git add scripts/generate.py tests/test_generate_cli.py
git commit -m "refactor(generate): delegate to library; stable filename across modes"
```

---

## Task 3: Shell out to `overlay_text.py` from the library

**Objective:** `scripts/pipeline/typography.py` becomes a thin wrapper that shells out to the existing `scripts/overlay_text.py`. One source of truth for the ImageMagick invocation. Constants stay in `overlay_text.py`.

**Files:**
- Create: `scripts/pipeline/typography.py`
- Test: `tests/test_typography.py`

**Why shell-out instead of re-implement:** Re-implementing the magick argv in `typography.py` doubles the constants (mask, x, y, body_x, point_size, line_height, font, label_color, body_color) and they will drift. The constants are also tuned for 1280×720 family B (out-of-scope bug for v1) — re-implementing locks them in twice. The shell-out keeps one file responsible for the argv.

**Step 1: Write test**

```python
# tests/test_typography.py
import sys
from pathlib import Path
from unittest.mock import patch

from scripts.pipeline.typography import overlay_typography


@patch("subprocess.run")
def test_overlay_typography_invokes_overlay_text(mock_run, tmp_path):
    src = tmp_path / "raw.jpg"
    src.write_bytes(b"\xff\xd8\xff\xe0fake jpeg")
    dst = tmp_path / "final.png"

    overlay_typography(
        src, dst,
        lines=[("SYSTEM", "32 language runtimes online"),
               ("NEW", "Full-stack AI MLOps")],
    )

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    # argv[0] is the python interpreter; the script path contains overlay_text.py.
    assert args[0] == sys.executable
    assert any("overlay_text.py" in a for a in args)
    # Lines must be passed via --line LABEL=copy.
    line_args = [a for a in args if a.startswith("SYSTEM=") or a.startswith("NEW=")]
    assert len(line_args) == 2
    assert "SYSTEM=32 language runtimes online" in line_args
    assert "NEW=Full-stack AI MLOps" in line_args


@patch("subprocess.run")
def test_overlay_typography_optional_font(mock_run, tmp_path):
    src = tmp_path / "raw.jpg"
    src.write_bytes(b"\xff\xd8\xff\xe0fake jpeg")
    dst = tmp_path / "final.png"

    overlay_typography(src, dst, lines=[("X", "y")],
                       font=Path("/System/Library/Fonts/Menlo.ttc"))
    args = mock_run.call_args[0][0]
    assert "--font" in args
    assert "/System/Library/Fonts/Menlo.ttc" in args
```

**Step 2: Implement**

```python
# scripts/pipeline/typography.py
import pathlib
import subprocess
import sys

# Delegate to scripts/overlay_text.py. Do NOT reimplement the ImageMagick
# argv here — overlay_text.py owns the constants because they're tuned for
# specific image dimensions and would drift if duplicated.

_OVERLAY_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "overlay_text.py"


def overlay_typography(
    src: pathlib.Path,
    dst: pathlib.Path,
    lines: list[tuple[str, str]],
    font: pathlib.Path | None = None,
) -> pathlib.Path:
    """Overlay literal copy lines on top of a generated image.

    Thin wrapper around scripts/overlay_text.py. See that script for
    ImageMagick tuning constants.
    """
    if not _OVERLAY_SCRIPT.is_file():
        raise FileNotFoundError(f"overlay_text.py not found: {_OVERLAY_SCRIPT}")
    if not src.is_file():
        raise FileNotFoundError(f"input not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(_OVERLAY_SCRIPT),
        "--input", str(src),
        "--output", str(dst),
    ]
    if font is not None:
        cmd += ["--font", str(font)]
    for label, body in lines:
        cmd += ["--line", f"{label}={body}"]

    subprocess.run(cmd, check=True)
    return dst
```

**Step 3: Real smoke test against existing raw image**

```bash
PYTHONPATH=. .venv/bin/python -c "
from pathlib import Path
from scripts.pipeline.typography import overlay_typography
overlay_typography(
    Path('outputs/B_brutalist_32_langs_raw.jpg'),
    Path('/tmp/test_overlay.png'),
    lines=[('SYSTEM','32 language runtimes online'),
           ('NEW','Full-stack · AI · MLOps'),
           ('READY','One agent. Every stack.')],
)
print('OK')
"
ls -la /tmp/test_overlay.png
```

Expected: `OK`; PNG exists, non-zero.

**Step 4: Run tests + commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_typography.py -v
git add scripts/pipeline/typography.py tests/test_typography.py
git commit -m "feat(pipeline): typography overlay shell-out to overlay_text.py"
```

---

## Task 4: Build the driver `scripts/run.py`

**Objective:** Single end-to-end entry point that takes a recipe + an image source (`--image-url` for remote or `--image-file` for local) + `--line` overlays and produces the final PNG. The driver is tool-agnostic — Hermes/operator drives the model call. `--image-file` exists specifically so the smoke test (and any local debug run) doesn't have to launder a path through a URL parser.

**Files:**
- Create: `scripts/run.py`
- Test: `tests/test_run.py`

**Step 1: Write test**

```python
# tests/test_run.py
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]


def test_dry_mode_prints_plan():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "run.py"),
         "--recipe", str(REPO / "recipes" / "live_test_recipe.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "32 LANGS" in out
    assert "Next:" in out


def test_download_rejects_non_http_schemes():
    """Guard against file:// and data: — the smoke test uses --image-file,
    so the URL guard must reject any URL that tries to read local files."""
    from scripts.run import download
    with pytest.raises(ValueError, match="refusing to fetch scheme"):
        download("file:///etc/passwd", Path("/tmp/x.jpg"))


def test_download_rejects_oversized_response(tmp_path):
    from scripts.run import download
    # Build a fake response that exceeds DOWNLOAD_MAX_BYTES in chunks.
    from unittest.mock import MagicMock, patch
    fake = MagicMock()
    fake.headers = {"Content-Type": "image/jpeg"}
    # One chunk of 1 MB repeated — small enough to allocate, large enough to exceed cap.
    big = b"\xff\xd8\xff" + b"x" * (1024 * 1024)
    def chunk_iter():
        for _ in range(30):  # 30 MB total, exceeds 25 MB cap
            yield big
    fake.__enter__ = lambda self: self
    fake.__exit__ = lambda self, *a: None
    fake.__iter__ = lambda self: chunk_iter()
    with patch("urllib.request.urlopen", return_value=fake):
        with pytest.raises(ValueError, match="exceeds"):
            download("http://example.com/huge.jpg", tmp_path / "x.jpg")


import pytest  # noqa: E402
```

**Step 2: Implement**

```python
#!/usr/bin/env python3
"""
run.py — End-to-end driver for the tech-image pipeline.

Reads a recipe, expects the operator (or a Hermes session) to supply the
image-generation result via --image-url (remote) or --image-file (local),
then overlays typography and writes the final artifact.

Typical use from a Hermes session:

    python scripts/run.py --recipe recipes/live_test_recipe.json \
        --image-url https://...raw.jpg \
        --line SYSTEM='32 language runtimes online' \
        --line NEW='Full-stack · AI · MLOps'

Local debug / smoke test:

    python scripts/run.py --recipe recipes/live_test_recipe.json \
        --image-file outputs/B_brutalist_32_langs_raw.jpg \
        --line SYSTEM='32 language runtimes online' ...

Dry mode (no image source): prints the rendered plan and exits 0.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
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
WEBP_MAGIC = b"RIFF"
IMAGE_MAGICS = (JPEG_MAGIC, PNG_MAGIC, WEBP_MAGIC)


def parse_line(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("line must be LABEL=copy")
    label, copy = value.split("=", 1)
    return label.strip(), copy.strip()


def download(url: str, dst: pathlib.Path) -> pathlib.Path:
    """Fetch a model-generated image into dst.

    Guards against:
      - non-http(s) schemes (no file://, no ftp://, no data:)
      - hangs (timeout)
      - unbounded size
      - HTML error pages being saved as .jpg (magic-byte check)

    The Content-Type header is intentionally NOT checked. CDNs frequently
    omit it for valid JPEGs, and the magic-byte check is sufficient.
    """
    if "://" not in url:
        raise ValueError(f"refusing to fetch non-URL: {url!r}")
    scheme = url.split("://", 1)[0].lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"refusing to fetch scheme {scheme!r}; allowed: {ALLOWED_SCHEMES}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "tech-image-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as r:
        chunks = []
        total = 0
        for chunk in r:
            total += len(chunk)
            if total > DOWNLOAD_MAX_BYTES:
                raise ValueError(f"download exceeds {DOWNLOAD_MAX_BYTES} bytes; aborting")
            chunks.append(chunk)
        body = b"".join(chunks)

    if not any(body.startswith(m) for m in IMAGE_MAGICS):
        raise ValueError(f"downloaded bytes do not look like an image (magic mismatch)")

    dst.write_bytes(body)
    return dst


def load_local(src: pathlib.Path, dst: pathlib.Path) -> pathlib.Path:
    """Copy a local file into dst. Magic-byte check, same as download()."""
    if not src.is_file():
        raise FileNotFoundError(f"input not found: {src}")
    body = src.read_bytes()
    if not any(body.startswith(m) for m in IMAGE_MAGICS):
        raise ValueError(f"local file is not a recognized image format: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(body)
    return dst


def main() -> int:
    p = argparse.ArgumentParser(description="Run the image pipeline end-to-end.")
    p.add_argument("--recipe", type=pathlib.Path, required=True)
    p.add_argument("--output-dir", type=pathlib.Path, default=ROOT / "outputs")
    img = p.add_mutually_exclusive_group()
    img.add_argument("--image-url", help="Raw generated image URL (from image_generate)")
    img.add_argument("--image-file", type=pathlib.Path,
                     help="Local raw generated image path (no scheme games)")
    p.add_argument("--font", type=pathlib.Path)
    p.add_argument("--line", type=parse_line, action="append", default=[],
                   help="LABEL=copy line to overlay. Pass multiple times.")
    args = p.parse_args()

    recipe = load_recipe(args.recipe)
    styles = load_styles(STYLES_PATH)
    style = get_family(styles, recipe.style)
    rendered = render_prompt(style, recipe.brief)
    out_final = output_path(args.output_dir, recipe.family_key,
                            recipe.brief["headline"], ".png")

    if not args.image_url and not args.image_file:
        print(f"[recipe]      {args.recipe}")
        print(f"[family]      {recipe.family_key}")
        print(f"[style]       {rendered['style']}")
        print(f"[aspect]      {rendered['aspect_ratio']}")
        print(f"[model]       {recipe.model} (n={recipe.n})")
        print("[prompt]")
        for line in rendered["prompt"].splitlines():
            print(f"  {line}")
        print(f"[output]      {out_final}")
        print("Next: call image_generate with the prompt, then re-run with --image-url or --image-file.")
        return 0

    raw = output_path(args.output_dir, recipe.family_key,
                      recipe.brief["headline"], "_raw.jpg")

    if args.image_url:
        print(f"[download]    {args.image_url} -> {raw}")
        download(args.image_url, raw)
    else:
        print(f"[copy]        {args.image_file} -> {raw}")
        load_local(args.image_file, raw)

    if not args.line:
        print("[warn]        no --line supplied; writing raw only (no overlay)")
        out_final = raw.with_suffix(".png")
        out_final.write_bytes(raw.read_bytes())
    else:
        overlay_kwargs = {"font": args.font} if args.font else {}
        overlay_typography(raw, out_final, lines=args.line, **overlay_kwargs)

    print(f"[done]        {out_final}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 3: Run test + dry smoke**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_run.py -v

# Dry mode prints plan
PYTHONPATH=. .venv/bin/python scripts/run.py --recipe recipes/live_test_recipe.json
```

Expected: 3 passed; dry mode prints plan and exits 0.

**Step 4: Commit**

```bash
git add scripts/run.py tests/test_run.py
git commit -m "feat(pipeline): end-to-end driver with --image-url and --image-file"
```

---

## Task 5: Topic-expansion helper (optional LLM path)

**Objective:** `expand_brief(topic)` shells out to an LLM CLI to fill the brief slots. `parse_brief_response` extracts JSON using `json.JSONDecoder.raw_decode` — no regexes, handles nested objects and prose-with-braces correctly. The DEFAULT_PROMPT must not crash on its own prose (braces in the icon list), so we use `.replace()` instead of `.format()`.

**Files:**
- Create: `scripts/pipeline/expand.py`
- Test: `tests/test_expand.py`

**Step 1: Write tests**

```python
# tests/test_expand.py
import pytest

from scripts.pipeline.expand import parse_brief_response


def test_parse_fenced_json():
    text = """Here's the brief:
```json
{"topic": "...", "headline": "32 LANGS", "icon": "globe", "aspect": "16:9"}
```
Hope that helps!"""
    out = parse_brief_response(text)
    assert out["headline"] == "32 LANGS"
    assert out["aspect"] == "16:9"


def test_parse_unfenced_json():
    """Regression: prior regex fell through to .group(1) on no capture group,
    throwing IndexError. Must handle plain JSON-with-prose."""
    text = """Sure, here's a brief for that topic:

{"topic": "...", "headline": "32 LANGS", "icon": "globe", "aspect": "16:9"}

Let me know if you want changes."""
    out = parse_brief_response(text)
    assert out["headline"] == "32 LANGS"
    assert out["aspect"] == "16:9"


def test_parse_nested_json_picks_outer_object():
    """Regression: a regex like \\{[^{}]*\\} matches the innermost object,
    silently returning the wrong brief. raw_decode must find the outer
    object even when nested ones appear in the prose."""
    text = """Brief:

{"headline": "X", "palette": {"accent": "#fff"}, "aspect": "16:9"}

Done."""
    out = parse_brief_response(text)
    assert out["headline"] == "X"
    assert out["aspect"] == "16:9"
    # Nested palette should be present, not the returned object.
    assert "palette" in out


def test_parse_prose_with_braces_then_real_object():
    """A common LLM failure mode: 'pick from {gear, lightning, ...}' prose
    followed by the actual JSON object. Both regex-based approaches
    matched the brace list. raw_decode walks to the real object."""
    text = """Pick from {gear, lightning, globe} based on the topic.

{"topic": "t", "headline": "X", "icon": "globe", "aspect": "16:9"}"""
    out = parse_brief_response(text)
    assert out["headline"] == "X"
    assert out["icon"] == "globe"


def test_parse_garbage_raises():
    with pytest.raises(ValueError, match="could not extract JSON"):
        parse_brief_response("Sorry, I can't help with that.")


def test_expand_brief_survives_braces_in_default_prompt():
    """Regression: DEFAULT_PROMPT contains '{gear, lightning, ...}' which
    str.format() reads as a field name, raising KeyError on every call.

    Uses a Python stub for the LLM CLI (instead of a mock) so the test
    actually exercises the subprocess path. Reverting expand_brief to
    .format() makes this test raise KeyError on the first call.
    """
    import sys
    stub_cmd = [
        sys.executable, "-c",
        "import sys; sys.stdin.read(); "
        "print('{\"topic\":\"t\",\"headline\":\"X\",\"icon\":\"globe\",\"aspect\":\"16:9\"}')"
    ]
    out = expand_brief("test topic", llm_cmd=stub_cmd)
    assert out["headline"] == "X"
    assert out["icon"] == "globe"
```

**Step 2: Implement**

```python
# scripts/pipeline/expand.py
import json
import subprocess

DEFAULT_PROMPT = """You are a brief-expander for a tech-image generator.

Given a topic, produce a JSON object with these fields:
- topic: one-sentence summary
- headline: 1-3 words, ALL CAPS, suitable for overlay
- icon: motif from {gear, lightning, globe, skull, brain, rocket, lock}
- aspect: 16:9, 4:5, 1:1, or 9:16
- mood: 1-2 word feel descriptor

Pick icon and aspect based on the topic. Use the style B (Sci-fi brutalist UI)
default unless the topic calls for something else.

Respond with ONLY a JSON code block. No prose outside the block.

Topic: {topic}
"""


def parse_brief_response(text: str) -> dict:
    """Find the first valid JSON object in the LLM response.

    Uses json.JSONDecoder.raw_decode — handles nested objects and
    prose-with-braces correctly. Regexes don't (see regression tests).
    """
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(text, i)
            return obj
        except json.JSONDecodeError:
            continue
    raise ValueError(f"could not extract JSON from LLM response: {text[:200]!r}")


def expand_brief(
    topic: str,
    llm_cmd: list[str],
    prompt_template: str = DEFAULT_PROMPT,
    timeout: int = 60,
) -> dict:
    """Shell out to an LLM CLI to expand a topic into a brief.

    llm_cmd is the command prefix; the prompt is passed via stdin.
    Example: llm_cmd = ["hermes", "chat", "--provider", "minimax-oauth",
                        "-m", "MiniMax-M3", "--cli", "--source", "tool"]

    Note: uses .replace() not .format(). The prose contains brace lists
    like "{gear, lightning, ...}" that .format() would read as field names.
    """
    prompt = prompt_template.replace("{topic}", topic)
    result = subprocess.run(
        llm_cmd, input=prompt, capture_output=True,
        text=True, timeout=timeout, check=True,
    )
    return parse_brief_response(result.stdout)
```

**Step 3: Run tests + commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_expand.py -v
git add scripts/pipeline/expand.py tests/test_expand.py
git commit -m "feat(pipeline): topic expansion with robust JSON extraction"
```

---

## Task 6: Author the in-repo SKILL.md

**Objective:** Place a SKILL.md at `skills/tech-image-pipeline/SKILL.md` that tells any future Hermes session how to use this project.

**Files:**
- Create: `skills/tech-image-pipeline/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: tech-image-pipeline
description: Use when generating brand-consistent tech/AI social images via the funsaized/tech-image-pipeline. Renders a brief into one of seven style families, calls image_generate, overlays literal copy via ImageMagick. Trigger when the user asks for "an image for X post" or wants the pipeline run.
---

# Tech-Image Pipeline

A seven-family brand-image pipeline. Python does the deterministic work; Hermes does the model work.

## When to use

- User asks for a brand-consistent image for a post, announcement, or feature.
- User references families A–G or the Teknium-style aesthetic.
- User has a topic and wants a brief expanded into a full image.

## Architecture

- `scripts/pipeline/` — library: `render`, `recipe`, `paths`, `styles`, `typography`, `expand`.
- `scripts/generate.py` — CLI; renders prompt + plan; supports `--call --emit-json`.
- `scripts/run.py` — end-to-end driver; accepts `--image-url` (remote) or `--image-file` (local).
- `scripts/overlay_text.py` — ImageMagick-driven typography overlay. **Single source of truth** for magick argv constants; do not reimplement in `pipeline/typography.py`.
- `templates/styles.json` — the seven family recipes.
- `recipes/*.json` — saved briefs for repeatable runs.

## Workflow

1. Load this skill: `skill_view(name="tech-image-pipeline")`.
2. Read `templates/styles.json` and pick the right family for the topic.
3. If the user provided only a topic (no full brief), call `expand_brief()` to fill the slots.
4. Render the prompt:
   ```bash
   PYTHONPATH=. python scripts/generate.py --recipe recipes/<name>.json --call --emit-json
   ```
5. Take the JSON envelope, call `image_generate` with `prompt`/`negative_prompt`/`aspect_ratio`/`model`/`n`.
6. Take the returned URL, run:
   ```bash
   PYTHONPATH=. python scripts/run.py --recipe recipes/<name>.json \
     --image-url <url> \
     --line SYSTEM='...' --line NEW='...' --line READY='...'
   ```
7. For local debug or smoke testing, use `--image-file <path>` instead of `--image-url`.

## Conventions

- Headlines are 1–3 words, ALL CAPS, ASCII-friendly.
- Aspect defaults: feature posts → 16:9, mobile → 4:5, square → 1:1.
- Always overlay literal copy via `overlay_typography`. The image model is responsible for layout, not copy.
- Output scope is content creation only. No publishing, posting, or upload helpers belong in this project.

## Verification

After a successful run, verify:
- `outputs/<family>_<headline>.png` exists and is non-zero.
- The overlay lines are readable (red label, cyan body, monospace).
- The headline renders in the image at the size dictated by the family template.

## Pitfalls

- `image_generate` returns a URL, not bytes. Pass it to `run.py --image-url`.
- `--image-url` rejects `file://`, `data:`, and other non-http(s) schemes. Use `--image-file` for local paths.
- Family `B_brutalist` is the most-tested. Other families are real templates but haven't been through end-to-end yet.
- `overlay_text.py` masks are tuned for 1280×720 (family B). Other aspects produce artifacts at the overlay boundaries — out of scope for v1.
- The `n` field on a recipe means "request N candidates from image_generate." The pipeline itself only consumes one; pick manually after seeing them.
- Output paths are deterministic. A second run against the same recipe silently overwrites both the raw download and the final PNG. Copy elsewhere if you need to keep an old artifact.
```

**Step 2: Commit**

```bash
git add skills/tech-image-pipeline/SKILL.md
git commit -m "docs(skill): add in-repo SKILL.md for tech-image-pipeline"
```

---

## Task 7: Tighten README §7/§9 + real smoke test

**Objective:** Rewrite README §7/§9 to match reality. Add a real smoke test that exercises the full driver path with `--image-file` and asserts a pixel-level diff against the existing reference within tolerance.

**Files:**
- Modify: `README.md` (§7, §9)
- Test: `tests/test_smoke_e2e.py`

**Calibration anchor:** `magick compare -metric AE outputs/B_brutalist_32_langs_verified.png outputs/B_brutalist_32_langs_verified.png` reports 0 differing pixels — the reference is bit-for-bit reproducible from the raw jpg with `overlay_text.py` defaults. Empirically measured regressions (drop a line, change color, shift x/y, change point-size) all produce ≥870 differing pixels, well above the floor.

```
TOLERANCE_PIXELS = 200   # exact render is 0; smallest measured regression is 870.
                         # Slack is for ImageMagick version drift only, not layout.
```

Catches all five measured regressions. Keep `-fuzz 1%` to absorb antialiasing rounding without admitting layout drift.

**Step 1: Write smoke test**

```python
# tests/test_smoke_e2e.py
"""End-to-end smoke test against the existing reference artifact.

Runs scripts/run.py with --image-file against outputs/B_brutalist_32_langs_raw.jpg,
then asserts the produced PNG matches outputs/B_brutalist_32_langs_verified.png
within 1% pixel difference (calibrated: existing artifacts differ by 0.23%).
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "outputs" / "B_brutalist_32_langs_raw.jpg"
REFERENCE = REPO / "outputs" / "B_brutalist_32_langs_verified.png"
TOTAL_PIXELS = 1280 * 720  # 921600
TOLERANCE_PIXELS = 200      # exact render: 0; smallest measured regression: 870


@pytest.mark.skipif(not shutil.which("magick"), reason="ImageMagick not installed")
@pytest.mark.skipif(not RAW.exists() or not REFERENCE.exists(),
                    reason="reference artifacts missing")
def test_driver_reproduces_reference_within_tolerance(tmp_path):
    """Run scripts/run.py end-to-end against the existing raw jpg with three
    overlay lines, then magick-compare against the verified reference."""
    out_dir = tmp_path / "smoke"
    out_dir.mkdir()
    final_png = out_dir / "B_brutalist_32_langs.png"

    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "run.py"),
         "--recipe", str(REPO / "recipes" / "live_test_recipe.json"),
         "--image-file", str(RAW),
         "--line", "SYSTEM=32 language runtimes online",
         "--line", "NEW=Full-stack · AI · MLOps",
         "--line", "READY=One agent. Every stack.",
         "--output-dir", str(out_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"driver failed: {result.stderr}"
    assert final_png.exists(), f"expected {final_png} to exist"
    assert final_png.stat().st_size > 0

    # Pixel diff via magick compare.
    cmp = subprocess.run(
        ["magick", "compare", "-metric", "AE", "-fuzz", "1%",
         str(REFERENCE), str(final_png), str(tmp_path / "diff.png")],
        capture_output=True, text=True,
    )
    # magick compare prints "N (P)" on stderr where N is the absolute pixel
    # count and P is the ratio. Tolerate either format.
    out = (cmp.stderr or "") + (cmp.stdout or "")
    first_token = out.strip().split()[0] if out.strip() else ""
    diff_pixels = int(float(first_token))
    assert diff_pixels <= TOLERANCE_PIXELS, (
        f"pixel diff {diff_pixels} exceeds tolerance {TOLERANCE_PIXELS} "
        f"(floor=0; smallest measured regression=870)"
    )
```

**Step 2: Edit §7**

Replace the current §7 with:

```markdown
## 7. Quick-start (what runs today)

The Python side renders the prompt and overlays typography. The model call
and candidate selection are made by a Hermes session or by hand.

```bash
# 1. Render the prompt + plan
PYTHONPATH=. python scripts/generate.py \
  --topic "Hermes Agent now supports 32 new languages" \
  --style B --aspect 16:9 --headline "32 LANGS" --icon "globe"

# 2. (Hermes session) call image_generate with the printed prompt.
#    Save the returned URL.

# 3. Overlay literal copy and write final PNG
PYTHONPATH=. python scripts/run.py --recipe recipes/live_test_recipe.json \
  --image-url <url-from-step-2> \
  --line SYSTEM='32 language runtimes online' \
  --line NEW='Full-stack · AI · MLOps' \
  --line READY='One agent. Every stack.'
```

Output: `outputs/B_brutalist_32_langs.png`.

For local debug or smoke testing, replace `--image-url` with `--image-file <path>`.

Dry mode (no image source) prints the rendered plan and exits 0 — safe to run before the model call has been made.
```

**Step 3: Replace §9**

```markdown
## 9. Roadmap

| Stage | Status | Owner |
|---|---|---|
| Prompt rendering from styles.json | done | library |
| ImageMagick typography overlay | done | library (shells to `overlay_text.py`) |
| Recipe loader + driver (`run.py`) | done | library |
| In-repo SKILL.md | done | docs |
| Real `image_generate` call from driver | not done | operator/Hermes |
| Topic-expansion helper (`expand_brief`) | done (library only) | library |
| Post → brief ingestion (URL or scraped post → brief) | **adjacent project, not v1** | future |
| Video augmentation | **out of scope for v1** — see risks below | — |
| CLIP-based candidate scoring | not done | future |
| Aspect-aware overlay masks | not done | future |
| Calendar rotation tool | not done | future |

**Why video is out of v1:** image-to-video models warp small monospaced glyphs (the [SYSTEM]/[NEW]/[READY] overlay at 25pt Menlo) under any motion prompt. Adding video safely requires choosing between (a) overlaying after the video pass, (b) replacing the Menlo+magick path with ffmpeg drawtext, or (c) compositing the still-overlay PNG over each video frame. Each is a separate design decision; deferred.

**Why post → brief is out of v1:** this pipeline writes outward (model APIs, filesystem); post → brief ingestion reads inward (untrusted URLs, scraped content). Different trust boundary, different error budget, different invariant (the source post vs. the literal copy). It's a real plan task — HTML/OG scraping, relevance check, "riff on this" prompt — that deserves its own project, not a roadmap row.
```

**Step 4: Verify no stale references**

```bash
grep -n "pipelines/\|MealOps\|from MealOps root" README.md
```

Expected: no output.

**Step 5: Run all tests + commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest -v
git add README.md tests/test_smoke_e2e.py
git commit -m "docs(readme): align §7 with what actually runs; tighten §9; defer video"
```

---

## Files Likely to Change

| File | Action |
|---|---|
| `requirements-dev.txt` | create (Task 0) |
| `.gitignore` | create (Task 0) |
| `scripts/pipeline/__init__.py` | create (Task 1, empty) |
| `scripts/pipeline/render.py` | create (Task 1, list-join preserved) |
| `scripts/pipeline/recipe.py` | create (Task 1, exports FAMILY_KEYS) |
| `scripts/pipeline/paths.py` | create (Task 1) |
| `scripts/pipeline/styles.py` | create (Task 1) |
| `scripts/pipeline/typography.py` | create (Task 3, shell-out) |
| `scripts/pipeline/expand.py` | create (Task 5, raw_decode + .replace) |
| `scripts/generate.py` | rewrite (Task 2, FAMILY_KEYS not "_x") |
| `scripts/run.py` | create (Task 4, --image-url + --image-file) |
| `scripts/overlay_text.py` | unchanged |
| `templates/styles.json` | fix `C_patent` missing `{headline}` (Task 1) |
| `tests/test_pipeline.py` | create (Task 1, 8 tests) |
| `tests/test_generate_cli.py` | create (Task 2, 4 tests) |
| `tests/test_typography.py` | create (Task 3, 2 tests) |
| `tests/test_run.py` | create (Task 4, 3 tests) |
| `tests/test_expand.py` | create (Task 5, 6 tests) |
| `tests/test_smoke_e2e.py` | create (Task 7, real e2e + dry sanity) |
| `skills/tech-image-pipeline/SKILL.md` | create (Task 6) |
| `README.md` | edit §7, §9 (Task 7) |

## Tests / Validation

- `pytest tests/ -v` — all tests pass.
- Manual: `python scripts/generate.py --recipe recipes/live_test_recipe.json --call --emit-json` returns a valid envelope.
- Manual: feed envelope to `image_generate`, take URL, run `scripts/run.py --image-url <url> --line ...`. Final PNG in `outputs/`.

## Risks & Tradeoffs

- **Driver doesn't call image_generate directly.** Every end-to-end run needs a Hermes session or operator to feed the image URL. Intentional seam.
- **`--image-file` exists for the smoke test and local debug.** Production runs use `--image-url`. The two paths share the same magic-byte check, so a successful local run is a strong proxy for the remote path.
- **No CLIP scorer.** `n > 1` means request N candidates from image_generate, then pick one by hand. The pipeline consumes one URL. Documented in SKILL.md pitfalls.
- **Output paths are deterministic.** A second run against the same recipe silently overwrites both the `_raw.jpg` download and the final PNG. Documented in SKILL.md; no `--force` flag in v1 — if you want to preserve an older artifact, copy it elsewhere first.
- **overlay_text.py constants are tuned for 1280×720.** Other aspects produce overlay artifacts at the boundary. Out of scope for v1; documented.
- **Video augmentation deferred.** Will require choosing between three overlay-preservation strategies; not bundled into the same plan.
- **No git repo yet.** Run `git init` and an initial commit before Task 1 if needed.

## Open Questions

- Should the overlay mask constants move into `templates/styles.json` so each family declares its own? (Better long-term; future plan task.)
- Should `download()` live in `scripts/pipeline/` so `run.py` and any future caller share the guard? (Yes — refactor candidate once a second caller exists.)
- Should `expand_brief` gain a CLI (`scripts/expand.py`)? (Library-only per plan; CLI ergonomics left to future work.)