# Lith

Lith renders a short brief into a style-locked image-generation prompt, and
overlays literal copy onto the image that comes back. It is a prompt renderer
and a typography compositor with a recipe format between them.

**What lith is.** Seven fixed visual style families in
[`styles.json`](src/lith/data/styles.json), each a prompt template with a few
substitution slots. A JSON recipe format that makes a brief re-runnable. A
deterministic ImageMagick pass that paints your literal copy over the image so
no shipped character was hallucinated. Two console scripts and a seven-function
Python API. Standard library only — the sole external binary is `magick`.

**What lith is not.** It is not an image generator: no API keys, no vendor SDK,
no model call anywhere in the codebase. `lith-generate --call` emits a JSON
envelope; you or an agent make the call and hand the result back through
`--image-url` or `--image-file`. It does not score or rank candidates, does not
post to any platform, does not do video, and does not turn an existing post
into a brief. Those stages are people, and lith is explicit about the handoff:
`lith-run` with no image source prints its plan and exits 0.

New here? Work through
[Tutorial: your first announcement image](docs/tutorial-first-image.md) — a
brief to a finished PNG in five steps, no API key required.

Why the pipeline stops where it does:
[About the pipeline](docs/explanation-pipeline.md). Why there are seven
families and what they share: [About the design language](docs/explanation-design-language.md).

Driving lith from a Hermes session: [`skills/lith/SKILL.md`](skills/lith/SKILL.md),
and [how to install it](#install-the-hermes-skill).

---

## Contents

- [Install](#install)
- [Install the Hermes skill](#install-the-hermes-skill)
- [CLI reference](#cli-reference) — [`lith-generate`](#lith-generate) · [`lith-run`](#lith-run) · [`overlay_text.py`](#overlay_textpy)
- [Python API](#python-api) — full detail in [the API reference](docs/reference-python-api.md)
- [Recipe format](#recipe-format)
- [Style families](#style-families)
- [`styles.json` schema](#stylesjson-schema)
- [Output paths](#output-paths)
- [Tests](#tests)
- [Status](#status)

---

## Install

Requirements:

| | |
|---|---|
| Python | 3.10 or newer (the library uses PEP 604 union syntax) |
| [uv](https://docs.astral.sh/uv/) | `brew install uv` on macOS |
| ImageMagick 7 | `magick` on `$PATH`; needed only for the overlay pass |

As a tool:

```bash
uv tool install git+https://github.com/funsaized/lith
lith-generate --help
```

As a library in another project:

```bash
uv add git+https://github.com/funsaized/lith
```

As a contributor:

```bash
git clone https://github.com/funsaized/lith.git
cd lith
uv sync --extra test
```

`uv sync --extra test` creates `.venv/`, resolves `pyproject.toml`, and installs
the project editable, which places `lith-generate` and `lith-run` in the venv.

Verify:

```bash
uv run lith-generate \
  --topic "test" --style B --aspect 16:9 --headline "32 LANGS" --icon "globe"
uv run python -c "from lith import render_prompt"
```

Both print and exit 0.

---

## Install the Hermes skill

[`skills/lith/SKILL.md`](skills/lith/SKILL.md) lets a Hermes session drive the
two CLIs on your behalf. It is a workflow wrapper only — every deterministic
behavior lives in the `lith` package, which the skill assumes is already
installed. Install the package first; the skill is useless without it.

Hermes discovers skills at `~/.hermes/skills/<name>/SKILL.md`. Put lith's there.

**Symlink** — the right choice from a checkout, since edits to the repo copy
take effect on the next Hermes restart. Run it from the repository root:

```bash
mkdir -p ~/.hermes/skills
rm -rf ~/.hermes/skills/lith
ln -s "$PWD/skills/lith" ~/.hermes/skills/lith
```

The `rm -rf` is load-bearing. If a real directory is already at that path — a
copy install, or a version from before the skill shipped in this repository —
`ln -s` puts the link *inside* it at `~/.hermes/skills/lith/lith` and exits 0.
Nothing errors, and Hermes goes on loading the stale `SKILL.md`. Adding `-fn`
does not help; macOS cannot unlink a real directory that way.

**Copy** — for a checkout you intend to delete:

```bash
mkdir -p ~/.hermes/skills/lith
cp skills/lith/SKILL.md ~/.hermes/skills/lith/SKILL.md
```

If you installed lith with `uv tool install` and have no checkout, clone the
repository for the skill file alone:

```bash
git clone --depth 1 https://github.com/funsaized/lith.git /tmp/lith
mkdir -p ~/.hermes/skills/lith
cp /tmp/lith/skills/lith/SKILL.md ~/.hermes/skills/lith/SKILL.md
```

Restart Hermes. Its session-start loader reads the skills directory once at
startup, so a skill added or edited mid-session is not picked up.

Verify:

```bash
test -f ~/.hermes/skills/lith/SKILL.md && echo "skill resolves"
test ! -e ~/.hermes/skills/lith/lith  && echo "not nested"
lith-generate --help >/dev/null && lith-run --help >/dev/null && echo "cli ok"
```

All three lines must print. The second is what catches the nesting trap above —
the first passes either way.

Then ask the session for something the skill covers — "generate a family B
announcement image for X" — and confirm it reaches for `lith-generate --call
--emit-json` rather than improvising a prompt.

To update the skill after pulling: symlink installs need nothing but a Hermes
restart; copy installs need the `cp` re-run. To uninstall,
`rm -rf ~/.hermes/skills/lith`.

### What the skill instructs

Worth knowing before you hand a session the keys — the file itself is 90 lines
and worth reading:

- Render the envelope with `lith-generate --recipe ... --call --emit-json`,
  call an image model with its fields, then finish through `lith-run`.
- Use absolute paths for recipes and images.
- Ask the user to pick when candidate selection is subjective.
- **Never publish, post, or upload without separate authorization.**

The skill declares `platforms: [linux, macos]`. The overlay defaults point at
`/System/Library/Fonts/Menlo.ttc`, so a Linux session must pass `--font`.

---

## CLI reference

### `lith-generate`

Renders a brief into a prompt. Prints a human-readable summary by default;
with `--call`, prints a generation envelope instead.

```
lith-generate --recipe PATH [options]
lith-generate --topic TEXT --style {A..G} --headline TEXT [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--recipe` | path | — | Recipe file. Supplies the brief, `model`, and `n`. |
| `--topic` | str | — | One-sentence brief. Required without `--recipe`. |
| `--style` | `A`–`G` | — | Style family. Required without `--recipe`. |
| `--headline` | str | — | In-image headline. Required without `--recipe`. |
| `--aspect` | `16:9` `4:5` `1:1` `9:16` | family default | Aspect ratio. |
| `--icon` | str | `gear` | Motif substituted into `{icon}`. |
| `--n` | int | `4` | Candidate count recorded in the envelope. |
| `--seed` | int | `None` | Seed recorded in the envelope. |
| `--model` | `grok-imagine-image-quality` `grok-imagine-image` `gpt-image-1` `minimax-image` | `grok-imagine-image-quality` | Model recorded in the envelope. |
| `--out` | path | derived | Output path recorded in the envelope. |
| `--call` | flag | off | Emit the envelope instead of the summary. |
| `--emit-json` | flag | off | With `--call`, emit JSON rather than `key=value` lines. |

With `--recipe`, the recipe's `model` and `n` win and `--model` / `--n` are
ignored; `--seed`, `--out`, `--call`, and `--emit-json` still apply.

Envelope fields, in order: `prompt`, `negative_prompt`, `aspect_ratio`,
`model`, `n`, `seed`, `output_path`, `style`.

```bash
uv run lith-generate --recipe recipes/live_test_recipe.json --call --emit-json
```

Exit codes: `0` on success, `2` on an argparse error (including a missing
`--topic`/`--style`/`--headline` when `--recipe` is absent).

### `lith-run`

Ingests a generated image and overlays literal copy. With no image source, it
prints its plan and exits.

```
lith-run --recipe PATH [--image-url URL | --image-file PATH] [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--recipe` | path | **required** | Recipe file. |
| `--image-url` | url | — | HTTP(S) URL of the generated image. Mutually exclusive with `--image-file`. |
| `--image-file` | path | — | Local generated image. Mutually exclusive with `--image-url`. |
| `--line` | `LABEL=copy` | `[]` | Overlay line; repeatable. Label and copy must both be non-empty. |
| `--font` | path | `/System/Library/Fonts/Menlo.ttc` | Font passed to the overlay. |
| `--output-dir` | path | `./outputs` | Directory for the raw and final files. |

Three modes:

| Condition | Behavior |
|---|---|
| No `--image-url` and no `--image-file` | Prints recipe, family, style, aspect, model, prompt, and output path; exits 0. Nothing is written. |
| Image source, no `--line` | Writes the raw image only, warns `[warn] no --line supplied`; exits 0. |
| Image source and `--line` | Writes the raw image, overlays copy, writes the final PNG; exits 0. |

`--image-url` fetches under four guards: HTTP(S) schemes only, re-checked after
redirects; 30-second timeout; 25 MB ceiling enforced while streaming; and a
magic-byte check for JPEG, PNG, or WebP before any write. `--image-file` skips
the network guards, keeps the magic-byte check, and no-ops the copy if source
and destination resolve to the same path.

```bash
uv run lith-run \
  --recipe recipes/live_test_recipe.json \
  --image-file outputs/B_brutalist_32_langs_raw.jpg \
  --line SYSTEM='32 language runtimes online' \
  --line NEW='Full-stack · AI · MLOps' \
  --line READY='One agent. Every stack.'
```

Exit codes: `0` on success, `2` on an argparse error. A failed download, a
non-image body, or a nonzero `magick` exit raises and terminates with a
traceback.

### `overlay_text.py`

The overlay implementation, bundled inside the package at
`src/lith/overlay_text.py`. `lith-run` and `overlay_typography` invoke it as a
subprocess and forward only `--input`, `--output`, `--line`, and `--font`. Run
it directly to reach the layout constants.

| Flag | Type | Default |
|---|---|---|
| `--input` | path | **required** |
| `--output` | path | **required** |
| `--line` | `LABEL=copy` | **required**, repeatable |
| `--font` | path | `/System/Library/Fonts/Menlo.ttc` |
| `--point-size` | int | `25` |
| `--x` | int | `150` — label column |
| `--body-x` | int | `295` — copy column |
| `--y` | int | `405` — first baseline |
| `--line-height` | int | `40` |
| `--label-color` | hex | `#FF3030` |
| `--body-color` | hex | `#00E5FF` |
| `--mask` | `x1,y1 x2,y2` | `120,365 1165,515` |

Behavior: fills `--mask` with black, then draws each line as `[LABEL]` at
(`--x`, `--y` + *i* × `--line-height`) in `--label-color` and the copy at
(`--body-x`, same *y*) in `--body-color`.

The position defaults are tuned for a 1280×720 family-B panel and are wrong for
other aspects. Exit codes: `0` on success, `2` if `magick`, the input, or the
font is missing.

---

## Python API

`from lith import ...` exposes seven names. Full signatures, return shapes,
exception tables, and internals for every module —
**[Python API and implementation reference](docs/reference-python-api.md)**.

| Name | Signature | Purpose |
|---|---|---|
| `render_prompt` | `(style, brief=None) -> dict[str, str]` | Substitute a brief into a family template. Returns `prompt`, `negative_prompt`, `aspect_ratio`, `style`. |
| `load_recipe` | `(path) -> Recipe` | Read and validate a recipe file. |
| `overlay_typography` | `(src, dst, lines, font=None) -> Path` | Paint literal copy onto an image via ImageMagick. |
| `expand_brief` | `(topic, llm_cmd, ...) -> dict` | Expand a topic into a brief using an LLM command you supply. |
| `parse_brief_response` | `(text) -> dict` | First decodable JSON object in an LLM reply. |
| `output_path` | `(out_dir, family_key, headline, ext) -> Path` | Derive an artifact path. |
| `slug` | `(text) -> str` | Filename-safe slug; `"untitled"` when empty. |

```python
from lith import load_recipe, render_prompt

recipe = load_recipe("recipes/live_test_recipe.json")
rendered = render_prompt(recipe)
```

`Recipe`, `FAMILY_KEYS`, `REQUIRED_BRIEF_KEYS`, `load_styles`, `get_family`, and
`DEFAULT_PROMPT` are not in `__all__` but are importable from their modules and
used by both console scripts.

---

## Recipe format

A recipe is a JSON object. See
[`recipes/live_test_recipe.json`](recipes/live_test_recipe.json).

| Key | Type | Required | Default | Description |
|---|---|---|---|---|
| `style` | `"A"`–`"G"` | yes | — | Style family letter. |
| `brief` | object | yes | — | Substitution values; see below. |
| `name` | string | no | file stem | Recipe identifier. |
| `description` | string | no | `null` | Free text; not used at runtime. |
| `model` | string | no | `grok-imagine-image-quality` | Recorded in the envelope. |
| `n` | int | no | `4` | Candidate count recorded in the envelope. |
| `expected_output` | string | no | `null` | Reference artifact path; read by the smoke test, not the CLIs. |

`brief` keys:

| Key | Required | Used for |
|---|---|---|
| `topic` | yes | Validation and human context; not substituted into any template. |
| `headline` | yes | `{headline}` slot **and** the output filename. |
| `icon` | yes | `{icon}` slot. |
| `aspect` | yes | `aspect_ratio` in the envelope. |
| `volume` | no | `{volume}` slot; family C only. Defaults to `"1"`. |

```json
{
  "name": "live_test_recipe",
  "style": "B",
  "brief": {
    "topic": "Hermes Agent now supports 32 new languages",
    "headline": "32 LANGS",
    "icon": "globe",
    "aspect": "16:9",
    "volume": "1"
  },
  "model": "grok-imagine-image-quality",
  "n": 4
}
```

---

## Style families

Seven families, defined in [`src/lith/data/styles.json`](src/lith/data/styles.json).
That file is authoritative for prompt text; this table is the index.

| Letter | Key | Name | Default aspect | Template slots | Best for |
|---|---|---|---|---|---|
| A | `A_sticker` | Sticker / whisper-joke infographic | 16:9 | `{headline}` `{accent}` | Quick reactions, ship announcements, POV jokes |
| B | `B_brutalist` | Sci-fi brutalist UI | 16:9 | `{headline}` `{icon}` | Feature flagships, capability reveals |
| C | `C_patent` | Vintage technical manual / patent diagram | 4:5 | `{headline}` `{icon}` `{volume}` | How-it-works posts, educational threads |
| D | `D_manga` | Manga tape-insert / risograph | 1:1 | `{headline}` `{base_color}` | Release announcements, chapter framing |
| E | `E_screenshot` | Editorial screenshot polish | 16:9 | `{headline}` | UI demos, product launches |
| F | `F_woodcut` | Woodcut / analog engraving | 4:5 | `{headline}` `{icon}` | Sponsor announcements, team memos |
| G | `G_log` | Role-log / status dashboard | 16:9 | `{headline}` | Operational posts, build-in-public stats |

Slot resolution, per `render_prompt`:

| Slot | Source | Fallback |
|---|---|---|
| `{headline}` | `brief["headline"]` | `"NEW"` |
| `{icon}` | `brief["icon"]` | `"gear"` |
| `{volume}` | `brief["volume"]` | `"1"` |
| `{base_color}` | `palette["background"]` | `"#000000"` |
| `{accent}` | `palette["accent"]` | `"#00E5FF"` |

A palette field holding a list is joined with `" | "` — for example
`A_sticker`'s four accents render as
`#FF2E88 | #00E5FF | #F2FF00 | #FF6B35`. An empty list falls back to the
default.

Why the families exist, what they have in common, and how to rotate them:
[About the design language](docs/explanation-design-language.md).

---

## `styles.json` schema

```
version      string   schema version ("1.0.0")
description  string   free text
families     object   family key -> family object
rules        object   authoring constraints; advisory, not enforced at runtime
```

Family object:

| Field | Type | Read by | Description |
|---|---|---|---|
| `name` | string | `render_prompt` | Human-readable name returned as `style`. |
| `prompt_template` | string | `render_prompt` | `str.format` template; slots per the table above. |
| `negative_prompt` | string | `render_prompt` | Returned verbatim. |
| `default_aspect` | string | `render_prompt` | Used when the brief omits `aspect`. |
| `palette` | object | `render_prompt` | Only `background` and `accent` are substituted; other keys document the family. |
| `best_for` | string[] | — | Documentation. |
| `iconography` | string[] | — | Documentation; suggested `icon` values. |

`rules` — `max_accent_colors`, `max_words_in_image`,
`always_oversize_headline`, `always_one_decorative_motif`,
`prefer_asymmetric_composition`, `always_one_idea_per_image` — are an authoring
checklist. No code reads them.

Pass an alternate file with `load_styles(path)`; the CLIs always use the
bundled copy.

---

## Output paths

Both filenames derive from `output_path(dir, family_key, headline, ext)`:

| File | Pattern | Example |
|---|---|---|
| Raw (ingested image) | `{family_key}_{slug(headline)}_raw.jpg` | `outputs/B_brutalist_32_langs_raw.jpg` |
| Final (after overlay) | `{family_key}_{slug(headline)}.png` | `outputs/B_brutalist_32_langs.png` |

The directory is `--output-dir` for `lith-run` (default `./outputs`) and
`./outputs` for `lith-generate`. The raw file always carries a `.jpg`
extension regardless of the source format, and both files are overwritten
without prompting when a recipe is re-run.

`outputs/B_brutalist_32_langs_verified.png` is a committed reference artifact —
real Grok output for `recipes/live_test_recipe.json`, overlaid — used by the
tutorial and the smoke test.

---

## Tests

```bash
uv run pytest
```

Six modules under `tests/`, covering prompt rendering, both CLIs, the brief
expander, typography, and an end-to-end smoke test. The smoke test skips with a
clear message when the reference artifacts in `outputs/` are absent.

---

## Status

| Component | State |
|---|---|
| Prompt rendering from `styles.json` | done |
| Recipe loader and dry-run driver | done |
| ImageMagick typography overlay | done |
| Topic expansion (`expand_brief`) | done, library only — no CLI |
| Hermes `SKILL.md` wrapper | done, shipped in `skills/`; [installed manually](#install-the-hermes-skill) |
| Image-model call from the driver | not built — by design; see [About the pipeline](docs/explanation-pipeline.md#why-the-driver-never-calls-a-model) |
| Candidate scoring | not built |
| Aspect-aware overlay masks | not built |
| Video augmentation | out of scope; [rationale](docs/explanation-pipeline.md#deliberate-omissions) |
| Post → brief ingestion | out of scope; [rationale](docs/explanation-pipeline.md#deliberate-omissions) |
| Calendar rotation tool | not built |

---

## Documentation

| Document | Type | Read it when |
|---|---|---|
| [Tutorial: your first announcement image](docs/tutorial-first-image.md) | Tutorial | Learning the pipeline by running it once |
| [Python API and implementation reference](docs/reference-python-api.md) | Reference | Calling the library, or reading the internals |
| [About the pipeline](docs/explanation-pipeline.md) | Explanation | Understanding what's built, what isn't, and why |
| [About the design language](docs/explanation-design-language.md) | Explanation | Choosing a family, writing a prompt, judging a candidate |
| [`skills/lith/SKILL.md`](skills/lith/SKILL.md) | Agent instructions | Checking what a Hermes session will do on your behalf |
| This README | Reference | Looking up a flag, a field, or a signature |

MIT licensed. See [LICENSE](LICENSE).
