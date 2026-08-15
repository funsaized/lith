# Lith Migration: Proper Python Package + Hermes Skill

**Goal:** Restructure `lith` so (a) it's importable as a normal Python package
(`import lith`) without `PYTHONPATH` gymnastics, and (b) Hermes sessions
auto-discover the workflow through a SKILL.md installed under `~/.hermes/skills/`.
No Hermes plugin code — the skill is a thin instruction layer; the package
is the actual tool.

> **Status:** Proposed
> **Date:** 2026-08-15
> **Deciders:** funsaized (project owner)

---

## Context

The current shape:

```
tech-image-pipeline/
├── pyproject.toml                 # package = "lith", but library is at scripts/pipeline/
├── scripts/
│   ├── pipeline/                  # importable as scripts.pipeline.* only
│   ├── generate.py                # CLI driver
│   ├── run.py                     # CLI driver
│   └── overlay_text.py            # ImageMagick script
└── skills/lith/SKILL.md           # in-repo, not auto-loaded
```

Three frictions this creates for the Hermes session:

1. **`import lith` doesn't work.** A session that wants to use the library
   in-process has to do `sys.path.insert(0, "<path>")` then `from scripts.pipeline
   import ...`. That's session state on every call.

2. **`PYTHONPATH=.` on every CLI invocation.** `uv run python scripts/run.py
   …` works but spells out the project layout. With a real package install,
   `lith-run --recipe …` works from anywhere.

3. **The SKILL.md is in the project repo, not `~/.hermes/skills/`.** Hermes
   doesn't auto-load skills from arbitrary project directories. To make it
   discoverable today, the user has to symlink the project's `skills/lith/`
   into `~/.hermes/skills/lith/`, or paste the body into a session manually.

This plan addresses all three with one restructure.

---

## Decision

**Restructure to a `src/lith/` package layout and ship a single
`~/.hermes/skills/lith/SKILL.md` wrapper.** No plugin code, no entry-point
hooks, no `register_*` functions. The skill is instructions; the package is
the tool.

The Hermès skill layer is the right shape here because:

- lith is invoked by a session, not by a runtime hook. It doesn't need to
  intercept requests, manage state, or register toolsets.
- The memory-provider plugin pattern (Mnemosyne) is heavier — it ships
  `__init__.py` with `register_memory_provider()`, has `tools.py`, and
  hooks into the in-process Hermes DB. lith doesn't need any of that.
- A `~/.hermes/skills/lith/SKILL.md` is auto-loaded when the session
  matches its description trigger; the agent then knows to call
  `uv run --project <path> lith-run …` or `from lith import …`.

---

## Target Layout

```
tech-image-pipeline/
├── pyproject.toml                 # package = "lith", src layout
├── src/
│   └── lith/
│       ├── __init__.py            # public API: render_prompt, load_recipe, overlay_typography, expand_brief
│       ├── render.py              # was scripts/pipeline/render.py
│       ├── recipe.py              # was scripts/pipeline/recipe.py
│       ├── paths.py               # was scripts/pipeline/paths.py
│       ├── styles.py              # was scripts/pipeline/styles.py
│       ├── typography.py          # was scripts/pipeline/typography.py
│       └── expand.py              # was scripts/pipeline/expand.py
├── src/lith/cli/
│   ├── generate.py                # was scripts/generate.py
│   └── run.py                     # was scripts/run.py
├── src/lith/overlay_text.py       # was scripts/overlay_text.py
├── recipes/
├── templates/styles.json
├── tests/
│   ├── test_lith_render.py
│   ├── test_lith_recipe.py
│   ├── test_lith_typography.py
│   ├── test_lith_expand.py
│   ├── test_lith_cli.py
│   └── test_lith_smoke_e2e.py
├── docs/
├── README.md
├── LICENSE
└── uv.lock
```

Two important shape decisions:

  • **Use `src/lith/` not top-level `lith/`.** This prevents accidental
    imports of the source tree during tests (the `src/` layout forces
    pip/uv to install first). It's the modern Python best practice.

  • **Put the CLI scripts under `src/lith/cli/` not `src/lith/`.** Keeps
    the public API surface small (`from lith import render_prompt`), with
    the CLI scripts being implementation details that the entry points
    invoke via `lith.cli.generate:main` and `lith.cli.run:main`.

---

## Public API (the surface lith exposes)

After the migration, `import lith` gets:

```python
from lith import (
    render_prompt,           # -> dict{prompt, negative_prompt, aspect_ratio, style}
    load_recipe,             # -> Recipe dataclass
    output_path,             # -> pathlib.Path
    slug,                    # -> str (filesystem-safe)
    overlay_typography,      # -> pathlib.Path (delegates to ImageMagick)
    expand_brief,            # -> dict (LLM topic expansion)
    parse_brief_response,    # -> dict (LLM response parser)
)
```

The CLI scripts (`lith-generate`, `lith-run`) are still installed as
console scripts via `[project.scripts]` in `pyproject.toml`.

---

## Hermes Skill (the wrapper)

`~/.hermes/skills/lith/SKILL.md` (NOT in the project repo — installed once
to the user's `~/.hermes/skills/`):

```yaml
---
name: lith
description: Generate tech announcement images through seven style families.
version: 0.1.0
author: funsaized, Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [image-generation, social-media, branding, design]
    related_skills: []
---

# Lith

Use the `lith` Python package to generate tech announcement images through
seven style families. The package owns the deterministic work (prompt
rendering, recipe loading, typography overlay); this session owns the model
calls (image generation, optional topic expansion).

## When to use

- User asks for an image for a post, announcement, or feature.
- User references the seven style families A–G.
- User wants a topic expanded into a complete image brief.

## Prerequisites

- `lith` installed: `uv tool install git+https://github.com/funsaized/lith`
- ImageMagick 7 (`magick` on `$PATH`) for the typography overlay.

## How to run

Render a prompt:

```bash
lith-generate --recipe recipes/<name>.json --call --emit-json
```

Run the driver (after image_generate returns a URL):

```bash
lith-run --recipe recipes/<name>.json \
  --image-url <url> \
  --line SYSTEM='...' --line NEW='...' --line READY='...'
```

Or import in-process:

```python
from lith import render_prompt, load_recipe, overlay_typography
style = render_prompt(load_recipe("recipes/<name>.json"))
```

## Pitfalls

- `n` on a recipe is the *requested* candidate count. Select one manually.
- Output paths are deterministic. A second run overwrites silently.
- Overlay masks are tuned for 1280×720 family B; other aspects may show artifacts.

## Verification

- `lith-generate --help` exits 0.
- `lith-run --help` exits 0.
- `python -c "from lith import render_prompt"` exits 0.
- The smoke test `pytest tests/test_lith_smoke_e2e.py` reproduces
  `outputs/B_brutalist_32_langs_verified.png` to within 200 pixels of diff.
```

This skill lives at `~/.hermes/skills/lith/SKILL.md`, not in the project
repo. The project repo stays focused on the package.

---

## Migration Steps

### Step 1 — Create the new layout

```bash
mkdir -p src/lith/cli
git mv scripts/pipeline/render.py    src/lith/render.py
git mv scripts/pipeline/recipe.py    src/lith/recipe.py
git mv scripts/pipeline/paths.py     src/lith/paths.py
git mv scripts/pipeline/styles.py    src/lith/styles.py
git mv scripts/pipeline/typography.py src/lith/typography.py
git mv scripts/pipeline/expand.py    src/lith/expand.py
git mv scripts/pipeline/__init__.py  src/lith/__init__.py
git mv scripts/generate.py           src/lith/cli/generate.py
git mv scripts/run.py                src/lith/cli/run.py
git mv scripts/overlay_text.py       src/lith/overlay_text.py
rmdir scripts/pipeline scripts
```

### Step 2 — Update internal imports

Every relative import in `src/lith/cli/*.py` and the library modules
needs to change from `from scripts.pipeline.…` to either:

  - **Same-package:** `from lith import render_prompt` (cleanest)
  - **Module-local:** `from lith.render import render_prompt` (also fine)

Specifically:

  - `src/lith/cli/generate.py` and `src/lith/cli/run.py` import paths
    currently include `sys.path.insert(0, str(ROOT))` to make `scripts.pipeline`
    importable. After the move, this becomes unnecessary — `from lith import …`
    works as long as the package is installed (editable install via uv is
    fine for development).
  - `src/lith/typography.py` references the overlay script via
    `pathlib.Path(__file__).resolve().parents[1] / "overlay_text.py"`.
    After the move, that path becomes `parents[1] / "overlay_text.py"` from
    `src/lith/cli/typography.py` → which is wrong, since typography lives
    in `src/lith/`, not `src/lith/cli/`. Fix: `parents[0] / "overlay_text.py"`.

### Step 3 — Update `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "lith"
version = "0.1.0"
description = "..."
# ... (unchanged metadata)

[project.scripts]
lith-generate = "lith.cli.generate:main"
lith-run = "lith.cli.run:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"lith" = ["overlay_text.py"]
```

The `[tool.setuptools.packages.find]` with `where = ["src"]` is the
canonical way to declare a src-layout package. `package-data` includes
the overlay script so it ships with the wheel.

### Step 4 — Update tests

Tests currently import like:

```python
from scripts.pipeline.render import render_prompt
from scripts.pipeline.paths import output_path, slug
```

After the move:

```python
from lith import render_prompt, load_recipe, output_path, slug
```

This is also a rename opportunity:

```bash
git mv tests/test_pipeline.py      tests/test_lith_render.py
git mv tests/test_recipe.py        tests/test_lith_recipe.py  # if it existed separately
git mv tests/test_typography.py    tests/test_lith_typography.py
git mv tests/test_expand.py        tests/test_lith_expand.py
git mv tests/test_generate_cli.py  tests/test_lith_cli.py
git mv tests/test_run.py           tests/test_lith_cli_run.py  # or merge with cli tests
git mv tests/test_smoke_e2e.py     tests/test_lith_smoke_e2e.py
```

### Step 5 — Update README and docs

The README's install instructions change from:

```bash
git clone https://github.com/funsaized/lith.git
cd lith
uv sync --extra test
```

to (for end users, not contributors):

```bash
uv tool install git+https://github.com/funsaized/lith
lith-generate --help
```

For contributors (the only people who need `uv sync`):

```bash
git clone https://github.com/funsaized/lith.git
cd lith
uv sync --extra test
uv run pytest
```

The SKILL.md that lived at `skills/lith/SKILL.md` in the repo gets
**deleted from the repo**. It moves to `~/.hermes/skills/lith/SKILL.md`
in step 6.

### Step 6 — Install the skill

```bash
mkdir -p ~/.hermes/skills/lith
# Either: copy the SKILL.md from this plan into ~/.hermes/skills/lith/SKILL.md
# Or:     install it as part of the lith package install (see "Future work")
```

This is a one-line step for the user. Future work could automate it
(see below).

---

## What this plan is NOT

- **Not a plugin.** No `register_*` function, no entry-point discovery in
  pyproject, no `plugin.yaml`. The skill is instructions; the package is
  the tool.
- **Not a sub-project.** lith stays one repo. The skill lives separately
  because skills are a Hermes-level concept, not a project-level one.
- **Not breaking.** Every existing CLI invocation works after the move.
  `lith-generate --recipe X --call --emit-json` produces the same JSON
  envelope; `lith-run --recipe X --image-url …` produces the same PNG.

---

## Trade-off Analysis

| Aspect | Current shape | After migration |
|---|---|---|
| Library import | `sys.path.insert(0, ROOT); from scripts.pipeline import …` | `from lith import …` |
| CLI invocation | `uv run --project <path> python scripts/run.py …` | `lith-run …` (works from anywhere) |
| Skill discovery | Requires symlink or manual paste | Auto-loaded from `~/.hermes/skills/lith/` |
| Plugin code | None | Still none |
| Test imports | `from scripts.pipeline.X import …` | `from lith import …` |
| File count | ~24 | ~24 (no real change) |
| Public API surface | Implicit (no `__init__.py` re-exports) | Explicit (`src/lith/__init__.py` lists public names) |

The restructure is mostly a path rename. The actual behavioral changes
are: (a) `import lith` works globally, (b) `lith-generate` is on PATH,
(c) the skill auto-loads.

---

## Verification

After the migration, all of these must hold:

- [ ] `uv sync --extra test` succeeds and `import lith` works in `.venv`
- [ ] `uv tool install .` from the project root puts `lith-generate` and
      `lith-run` on global PATH
- [ ] `lith-generate --recipe recipes/live_test_recipe.json --call --emit-json`
      exits 0 and emits a JSON envelope with all 8 expected keys
- [ ] `lith-run --recipe recipes/live_test_recipe.json --image-file outputs/B_brutalist_32_langs_raw.jpg
      --line SYSTEM='…' --line NEW='…' --line READY='…'`
      reproduces `outputs/B_brutalist_32_langs_verified.png` to 0-pixel diff
- [ ] `uv run pytest` runs all 25 tests green
- [ ] No file in the repo references `scripts.pipeline` (grep clean)
- [ ] No file in the repo contains `from scripts.` (grep clean)
- [ ] `~/.hermes/skills/lith/SKILL.md` exists with valid frontmatter
      (yaml loads, `name: lith`, `description ≤ 60 chars`, ends with `.`)
- [ ] A fresh Hermes session can say "make me a tech announcement image"
      and the session auto-loads the skill and invokes `lith-generate`
      without the user pasting SKILL.md content

The last verification (Hermes auto-load) requires a session restart —
the skill loader is initialized at session start. That's expected.

---

## Future Work (out of scope for this migration)

These are reasonable follow-ups but not part of the v1 restructure:

  - **`pip install` from GitHub.** `uv tool install git+https://github.com/funsaized/lith`
    works after this migration. Documenting it on the README is sufficient.

  - **Publish to PyPI.** Once the package structure is real, `python -m build
    && twine upload dist/*` puts `lith` on PyPI for `pip install lith`. Adds
    discoverability and removes the GitHub-from-URL step for most users.

  - **Auto-install the skill.** A `pyproject.toml` `[project.entry-points."hermes.skills"]`
    block could let `lith` ship the SKILL.md and have Hermes pick it up on
    plugin discovery. But that requires Hermes to support skill entry-points,
    which today it doesn't (it scans `~/.hermes/skills/<name>/SKILL.md` only).
    Until that exists, the one-line `mkdir -p ~/.hermes/skills/lith && cp …`
    is fine.

  - **Migrate to optional-tier in hermes-agent repo.** If a future lith feature
    gets bundled with hermes-agent (e.g. a default template shipped to all
    users), `skills/creative/lith/SKILL.md` in the hermes-agent repo is the
    canonical home. Not relevant for v1.

---

## Decisions

1. **`src/lith/` layout, not top-level `lith/`.** Forces install-first
   semantics; prevents accidental local-tree imports during tests. Standard.

2. **Skill lives at `~/.hermes/skills/lith/`, not in the project repo.**
   Project repo stays focused on the package; skill is a Hermes-level
   resource the user installs once.

3. **No plugin code.** Lith is invoked by a session, not by the runtime.
   The skill is sufficient. If lith later needs to hook into the Hermes
   state (e.g. write metadata to session DB), revisit as a plugin.

4. **Tests keep their granularity but rename to `test_lith_*.py`.** Five
   separate test files is fine; the rename makes them grep-discoverable.

5. **CLI scripts move to `src/lith/cli/`.** Keeps the public API surface
   small. The `[project.scripts]` block changes to `lith.cli.generate:main`
   and `lith.cli.run:main`.

---

## Consequences

**Easier:**
- `import lith` from any Python, any session, any machine with the package
  installed.
- `lith-generate` and `lith-run` work from any cwd, not just the project
  root.
- Hermes sessions auto-discover the workflow through skill matching.
- Future PyPI release is a `python -m build` away.

**Harder:**
- One-time migration cost (~30 minutes of mechanical path edits + test
  updates). All work is reversible via `git revert`.
- The SKILL.md moves out of the repo. Anyone who relied on finding it at
  `skills/lith/SKILL.md` needs to know it now lives at `~/.hermes/skills/lith/SKILL.md`.
  The README change makes this explicit.

**Risks:**
- Test import paths must be updated atomically with the package paths.
  Tests that import old paths during the transition will fail. Mitigation:
  do the rename as one atomic commit, run tests, fix any path that
  wasn't covered by the grep.
- The `src/lith/overlay_text.py` is referenced by `src/lith/typography.py`
  via a `pathlib.Path` lookup. The path arithmetic needs to match the
  new directory structure. Mitigation: the typography test verifies this
  indirectly (it asserts the subprocess command works).

**Revisit triggers:**
- Hermes adds a skill entry-point mechanism → consider auto-installing
  the SKILL.md from the package.
- lith grows stateful behavior (e.g. persistent recipe cache, session
  metadata) → consider promoting to a real plugin.
- lith goes on PyPI → no migration needed, just `python -m build && twine
  upload`.

---

## Action Items

- [ ] Step 1 — Create `src/lith/` and `src/lith/cli/` directories
- [ ] Step 2 — `git mv` library modules and CLI scripts to new locations
- [ ] Step 3 — Update internal imports (every `from scripts.pipeline` →
        `from lith`)
- [ ] Step 4 — Fix `typography.py`'s path lookup for `overlay_text.py`
- [ ] Step 5 — Update `pyproject.toml`: src layout, `[project.scripts]`
        targets, `package-data`
- [ ] Step 6 — Update test imports + rename test files to `test_lith_*.py`
- [ ] Step 7 — Update README install + usage sections
- [ ] Step 8 — Delete `skills/lith/SKILL.md` from the project repo
- [ ] Step 9 — `uv sync --extra test` and `uv run pytest` (must be 25/25 green)
- [ ] Step 10 — `uv tool install .` from the project root; verify
        `lith-generate --help` and `lith-run --help` work globally
- [ ] Step 11 — `mkdir -p ~/.hermes/skills/lith && cp <skill-md> ~/.hermes/skills/lith/SKILL.md`
- [ ] Step 12 — Smoke test: `lith-run --recipe recipes/live_test_recipe.json
        --image-file outputs/B_brutalist_32_langs_raw.jpg --line …`
        reproduces `verified.png` to 0-pixel diff
- [ ] Step 13 — Commit as `refactor: migrate to src/lith package layout and Hermes skill`

---

## Provenance

This plan was produced after the rebrand-to-`lith` commit (`d66f19e`).
The current shape works but has the three frictions described in
"Context." The migration target is the minimum change that fixes all
three without introducing plugin complexity.