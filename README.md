# Lith

Lith renders a short brief into a style-locked image-generation prompt, calls
xAI, OpenAI, or MiniMax through one inspectable provider layer, then validates
and publishes the image that comes back.

**What lith is.** Seven fixed visual style families in
[`styles.json`](src/lith/data/styles.json), each a prompt template with a few
substitution slots. A JSON recipe format that makes a brief re-runnable. A
poster spec — headline, subtitle, sections, diagram, footer — serialized into
the prompt as a literal copy block the model is ordered to reproduce character
for character, so no shipped word was invented by the model. Fifteen named
layouts and a resolution chain that picks one from the shape of your content
and the shape of the frame. Three console scripts, six root-level convenience
functions, and a typed `lith.call` API. Standard library only, no vendor SDKs or
external binaries.

**What lith is not.** It is not a vendor SDK or an autonomous publisher.
`lith-call` performs generation, but it does not score or rank candidates, post
to any platform, do video, or turn an existing post into a brief. Candidate
selection and publication remain explicit handoffs; `lith-run` with no image
source prints its plan and exits 0.

New here? Work through
[Tutorial: your first announcement image](docs/tutorial-first-image.md) — a
brief to a finished image in five steps, no API key required.

Why the pipeline stops where it does:
[About the pipeline](docs/explanation-pipeline.md). How the same spec renders
seven ways: [About output styles](docs/explanation-output-styles.md). How panels
get arranged: [About layouts](docs/explanation-layouts.md). The palette and
composition rules underneath: [About the design language](docs/explanation-design-language.md).

Driving lith from a Hermes session: [`skills/lith/SKILL.md`](skills/lith/SKILL.md),
and [how to install it](#install-the-hermes-skill).

---

## Contents

- [Install](#install)
- [Install the Hermes skill](#install-the-hermes-skill)
- [CLI reference](#cli-reference) — [`lith-generate`](#lith-generate) · [`lith-call`](#lith-call) · [`lith-run`](#lith-run)
- [Python API](#python-api) — full detail in [the API reference](docs/reference-python-api.md)
- [Recipe format](#recipe-format)
- [Style families](#style-families)
- [Layouts](#layouts)
- [Aspect ratios](#aspect-ratios)
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
the project editable, which places `lith-generate`, `lith-call`, and `lith-run`
in the venv.

Verify:

```bash
uv run lith-generate \
  --topic "test" --style B --aspect 16:9 --headline "32 LANGS" --icon "globe"
uv run lith-call --help
uv run python -c "from lith import render_prompt"
```

All three print and exit 0.

---

## Install the Hermes skill

[`skills/lith/SKILL.md`](skills/lith/SKILL.md) lets a Hermes session drive the
three CLIs on your behalf. It is a workflow wrapper only — every deterministic
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
lith-generate --help >/dev/null && lith-call --help >/dev/null \
  && lith-run --help >/dev/null && echo "cli ok"
```

All three lines must print. The second is what catches the nesting trap above —
the first passes either way.

Then ask the session for something the skill covers — "generate a family B
announcement image for X" — and confirm it checks the route before generating
rather than improvising a prompt.

To update the skill after pulling: symlink installs need nothing but a Hermes
restart; copy installs need the `cp` re-run. To uninstall,
`rm -rf ~/.hermes/skills/lith`.

### What the skill instructs

Worth knowing before you hand a session the keys — the file is short and worth
reading in full:

- Run `lith-call --check`, generate with the selected route, then finish through
  `lith-run --strict`.
- Use absolute paths for recipes and images.
- Ask the user to pick when candidate selection is subjective.
- **Never publish, post, or upload without separate authorization.**
- Write the full poster spec into the brief, because every word in it is
  printed into the image verbatim.

The skill declares `platforms: [linux, macos]` and needs nothing beyond a
Python install on either.

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
| `--aspect` | provider ratio union | family default | One of `1:1` `3:4` `4:3` `9:16` `16:9` `2:3` `3:2` `9:19.5` `19.5:9` `9:20` `20:9` `1:2` `2:1` `21:9` `auto`. Use a concrete ratio for `lith-call`. |
| `--icon` | str | `gear` | Motif substituted into `{icon}`. |
| `--n` | int | `4` | Candidate count recorded in the envelope. |
| `--seed` | int | `None` | Seed recorded in the envelope. |
| `--model` | see [Aspect ratios](#aspect-ratios) | `grok-imagine-image-2.0` | Model recorded in the envelope for a later `lith-call`. |
| `--out` | path | derived stem | Output path recorded in the envelope, verbatim. Without it, the derived value carries no extension. |
| `--call` | flag | off | Emit the envelope instead of the summary. |
| `--emit-json` | flag | off | With `--call`, emit JSON rather than `key=value` lines. |

With `--recipe`, the recipe's `model` and `n` win and `--model` / `--n` are
ignored; `--seed`, `--out`, `--call`, and `--emit-json` still apply.

Envelope fields, in order: `prompt`, `negative_prompt`, `aspect_ratio`,
`model`, `n`, `seed`, `output_path`, `style`, `aspect_note`, `copy_note`,
`limit_notes`.
`aspect_note` is `null` unless the model forced a different ratio. `copy_note`
is `null` unless the copy block is too thin for the template around it — a
brief with no `sections` renders about sixteen characters of copy against
fifteen hundred of instructions, and the model starts lettering the
instructions instead. `limit_notes` names model-specific `n` or prompt-length
violations without changing the prompt.

```bash
uv run lith-generate --recipe recipes/live_test_recipe.json --call --emit-json
```

Exit codes: `0` on success, `2` on an argparse error (including a missing
`--topic`/`--style`/`--headline` when `--recipe` is absent).

### `lith-call`

Turns a rendered recipe into real candidate bytes through xAI, OpenAI, or
MiniMax. Inspect the route and exact provider payload before spending money.

```
lith-call --recipe PATH [--out DIR] [--n N] [--resolution {1k,2k}]
          [--quality {low,medium,high}] [--seed N]
          [--dry-run | --check | --auth] [--emit-json]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--recipe` | path | — | Recipe to render and call. Required except with `--auth`. |
| `--out` | directory | recipe's output directory | Candidate directory. Files are `{family_key}_{slug}-c{index}.{ext}`. |
| `--n` | int | recipe `n` | Overrides the candidate count for this call. Provider maxima are xAI/OpenAI 10 and MiniMax 9. |
| `--resolution` | `1k` `2k` | — | xAI resolution. Other adapters report it in `unsupported`. |
| `--quality` | `low` `medium` `high` | — | OpenAI quality. Other adapters report it in `unsupported`. |
| `--seed` | int | — | MiniMax seed. Other adapters report it in `unsupported`. |
| `--dry-run` | flag | off | Print the exact provider URL, redacted headers, request body, and unsupported fields; make no call. |
| `--check` | flag | off | Print whether Hermes `image_generate` or `lith-call` preserves the recipe's model and aspect; make no call. |
| `--auth` | flag | off | Report each provider's resolving credential tier and short fingerprint, never its value. `--recipe` is optional. |
| `--emit-json` | flag | off | Emit JSON for `--auth`, `--check`, or a live result. `--dry-run` is always JSON. |

`--dry-run`, `--check`, and `--auth` are mutually exclusive. A live call writes
one file per `CallResult.candidates` entry, choosing the extension from the
bytes rather than the model id. Human output also prints any reported model,
aspect, revised prompt, cost, and every `unsupported` field; JSON output carries
the same metadata plus the provider's raw response.

Credentials resolve in this order: shell environment, the recipe repository's
`.env`, `~/.hermes/.env`, then compatible OAuth entries in
`~/.hermes/auth.json`. The strict variable names are `XAI_API_KEY`,
`OPENAI_API_KEY`, and `MINIMAX_API_KEY`; copy [`.env.example`](.env.example) for
a repo-local setup. A repo `.env` is ignored by Git. `lith-call --auth` shows
which tier won.

MiniMax is implemented but its 1500-character prompt cap is lower than every
current integration recipe. The adapter raises before any network call and
names the measured length and cap; compact templates are a separate design
task.

```bash
uv run lith-call --check --recipe recipes/integration/24-aspect-ultrawide.json
uv run lith-call --dry-run --recipe recipes/integration/01-stack-A.json
uv run lith-call --recipe recipes/integration/01-stack-A.json --n 2 --emit-json
```

Exit codes: `0` on success and `2` on an argparse error. Credential, request,
transport, or provider failures terminate nonzero without writing candidates.

### `lith-run`

Validates a generated image and publishes it under the recipe's deterministic
path. With no image source, it prints its plan and exits.

```
lith-run --recipe PATH [--image-url URL | --image-file PATH] [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--recipe` | path | **required** | Recipe file. |
| `--image-url` | url | — | HTTP(S) URL of the generated image. Mutually exclusive with `--image-file`. |
| `--image-file` | path | — | Local generated image. Mutually exclusive with `--image-url`. |
| `--output-dir` | path | beside the recipe | Directory for the published file. Defaults to the recipe's sibling `outputs/`, not the cwd. |
| `--strict` | flag | off | Exit 1 when the delivered frame does not match the request. The file is still published. |

Two modes:

| Condition | Behavior |
|---|---|
| No `--image-url` and no `--image-file` | Prints recipe, family, style, aspect, model, prompt, and output path; exits 0. Nothing is written. |
| Image source | Writes the image to the recipe's output path, extension sniffed from the bytes; exits 0, or 1 under `--strict` if the frame drifted. |

`lith-run` is the only step that compares the delivered frame against the one
the prompt was composed for, so it is the only place a silently substituted
ratio becomes visible. Without `--strict` that comparison is a `[warn]` line on
stdout and the command still exits 0 — fine when a person is reading the
output, useless to a sweep script scraping exit codes. Pass `--strict` in
batches. The image is published either way, because the bytes are the evidence
you need to diagnose the substitution.

`--image-url` fetches under four guards: HTTP(S) schemes only, re-checked after
redirects; 30-second timeout; 25 MB ceiling enforced while streaming; and a
magic-byte check for JPEG, PNG, or WebP before any write. `--image-file` skips
the network guards, keeps the magic-byte check, and no-ops the copy if source
and destination resolve to the same path.

Bytes are staged as `<stem>.part` and renamed once the format is known, because
the extension cannot be chosen before the bytes are inspected. The published
extension follows the image, not the recipe: Grok returns JPEG, `gpt-image-1`
returns PNG. Nothing is re-encoded.

```bash
uv run lith-run \
  --recipe recipes/live_test_recipe.json \
  --image-file outputs/B_brutalist_32_langs_raw.jpg
```

Exit codes: `0` on success, `2` on an argparse error. A failed download or a
non-image body raises and terminates with a traceback.

---

## Python API

`from lith import ...` exposes six names. Full signatures, return shapes,
exception tables, and internals for every module —
**[Python API and implementation reference](docs/reference-python-api.md)**.

| Name | Signature | Purpose |
|---|---|---|
| `render_prompt` | `(style, brief=None) -> dict[str, str]` | Substitute a brief into a family template. Returns `prompt`, `negative_prompt`, `aspect_ratio`, `style`. |
| `load_recipe` | `(path) -> Recipe` | Read and validate a recipe file. |
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
used by the console scripts.

Provider calls live in the separate `lith.call` API:

```python
from lith import load_recipe, render_prompt
from lith.call import ImageRequest, generate

recipe = load_recipe("recipes/integration/01-stack-A.json")
rendered = render_prompt(recipe)
result = generate(ImageRequest(
    prompt=rendered["prompt"],
    model=recipe.model,
    aspect=rendered["aspect_ratio"],
    n=recipe.n,
    negative_prompt=rendered["negative_prompt"],
))
```

`result.candidates` always contains decoded bytes. `result.unsupported` makes
every supplied field the selected provider could not accept visible; no adapter
appends such a field to `prompt`. See the
[full `lith.call` reference](docs/reference-python-api.md#lithcall).

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
| `model` | string | no | `grok-imagine-image-2.0` | Recorded in the envelope. Not validated against the CLI's choices, so any model id passes through. |
| `n` | int | no | `4` | Candidate count recorded in the envelope. |

`brief` keys:

| Key | Required | Used for |
|---|---|---|
| `topic` | yes | Validation and human context; not substituted into any template. |
| `headline` | yes | The spec's `TITLE:` line **and** the output filename. |
| `icon` | yes | `{icon}` slot. |
| `aspect` | no | Pins the ratio. Omit to derive it from content shape, then the family default. |
| `volume` | no | `{volume}` slot; family C only. Defaults to `"1"`. |
| `title` | no | Overrides `headline` in the spec's `TITLE:` line only; the filename still uses `headline`. |
| `subtitle` | no | Spec `SUBTITLE:` line, and a subtitle zone in `{layout}`. |
| `sections` | no | List of `{heading, lines}` objects — the section panels. `heading` is required on each; `lines` is 2–4 strings. |
| `diagram` | no | One sentence naming every label in a simple drawing; adds a drawing zone. Described, not lettered — only the labels it names appear as text. |
| `diagram_position` | no | `below` (default) · `above` · `beside` · `center`. `radial` forces `center`. |
| `layout` | no | Arrangement for the section panels; see below. Omit to derive it from section count and frame shape. |
| `footer` | no | One short line under a horizontal rule. |
| `base_color` | no | Overrides the family palette's `background` in `{base_color}`. |
| `accent` | no | Overrides the family palette's `accent` in `{accent}`. |

All seven families carry `{spec}` and `{layout}`, so spec keys reach every one
of them. A brief with no `sections` degrades to a title-only spec, which is
what every pre-spec recipe produces.

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
  "model": "grok-imagine-image-2.0",
  "n": 4
}
```

---

## Style families

Seven families, defined in [`src/lith/data/styles.json`](src/lith/data/styles.json).
That file is authoritative for prompt text; this table is the index.

**Every family carries `{spec}` and `{layout}`.** The copy path is identical
across all seven — the brief supplies every word, the template supplies only
how those words are drawn. "Extra slots" below lists what a family uses
*beyond* those two.

| Letter | Key | Name | Default aspect | Extra slots | Best for |
|---|---|---|---|---|---|
| A | `A_sticker` | Sticker / whisper-joke infographic | 16:9 | `{accent}` | Quick reactions, ship announcements, POV jokes |
| B | `B_brutalist` | Sci-fi brutalist UI | 16:9 | `{icon}` | Feature flagships, capability reveals |
| C | `C_patent` | Vintage technical manual / patent diagram | 2:3 | `{icon}` `{volume}` | How-it-works posts, educational threads |
| D | `D_manga` | Manga tape-insert / risograph | 2:3 | `{base_color}` | Release announcements, chapter framing |
| E | `E_screenshot` | Editorial screenshot polish | 16:9 | — | UI demos, product launches |
| F | `F_woodcut` | Woodcut / analog engraving | 2:3 | `{icon}` | Sponsor announcements, team memos |
| G | `G_log` | Role-log / status dashboard | 16:9 | `{icon}` | Operational posts, build-in-public stats |

Slot resolution, per `render_prompt`:

| Slot | Source | Fallback |
|---|---|---|
| `{headline}` | `brief["headline"]` | `"NEW"` |
| `{icon}` | `brief["icon"]` | `"gear"` |
| `{volume}` | `brief["volume"]` | `"1"` |
| `{base_color}` | `brief["base_color"]`, else `palette["background"]` | `"#000000"` |
| `{accent}` | `brief["accent"]`, else `palette["accent"]` | `"#00E5FF"` |
| `{spec}` | the brief's copy fields, serialized | title-only block |
| `{layout}` | the zones the brief has copy for | title zone alone |

A palette field holding a list is joined with `" | "` — for example
`A_sticker`'s four accents render as
`#FF2E88 | #00E5FF | #F2FF00 | #FF6B35`. An empty list falls back to the
default. The brief wins over the palette, so a family listing three
backgrounds needs the recipe to name one, or the prompt asks for a "single
flat background" and then lists three colors.

### Layouts

`brief.layout` selects how section panels are arranged. Omit it and lith derives
one from the panel count and the frame's orientation.

| Key | Arrangement |
|---|---|
| `stack` | One full-width column |
| `two-column` · `three-column` | Balanced columns |
| `grid-2x2` · `grid-2x3` · `grid-3x2` · `grid-3x3` | Strict grids |
| `hero` | First panel full width at double height, rest in a grid beneath |
| `sidebar` | First panel a tall left rail, rest stacked to its right |
| `timeline` | Vertical sequence on a spine, each panel stepped right |
| `radial` | Panels ringed around a centred drawing on leader lines |
| `masonry` | Two columns of unequal height, no two tops aligned |
| `zigzag` | Alternating left/right, offset and rotated a degree or two |
| `split` | Two facing groups either side of one strong rule |
| `diagonal` | Stepping upper-left to lower-right, corners overlapping |

Derived when `layout` is absent:

| Panels | Portrait | Landscape |
|---|---|---|
| 1 | `stack` | `stack` |
| 2 | `two-column` | `two-column` |
| 3 | `hero` | `three-column` |
| 4 | `grid-2x2` | `grid-2x2` |
| 5 | `hero` | `hero` |
| 6 | `grid-2x3` | `grid-3x2` |
| 7–9 | `two-column` | `grid-3x3` |

Column counts cap at two in portrait: three narrow columns of body copy in a
tall frame is where legibility goes first.

Why the families exist, what they have in common, and how to rotate them:
[About the design language](docs/explanation-design-language.md).

---

## Aspect ratios

`brief.aspect` pins a ratio. Omit it and lith resolves one, in this order:

1. `brief.aspect`, when set
2. content shape — 3+ sections resolve portrait `2:3`, 1–2 resolve `1:1`
3. the family's `default_aspect`
4. `16:9`

Whatever those choose is then clamped to what the recipe's `model` can actually
produce. A model does not reject a ratio it lacks; it silently substitutes one,
so lith substitutes first and says so.

| Model | Capability variant | Limit |
|---|---|---|
| `grok-imagine-image-2.0` (**default**) | ratio enum | `1:1` `3:4` `4:3` `9:16` `16:9` `2:3` `3:2` `9:19.5` `19.5:9` `9:20` `20:9` `1:2` `2:1` (`auto` is recorded but never sent) · `n ≤ 10` |
| `grok-imagine-image-quality`, `grok-imagine-image` | ratio enum | `1:1` `16:9` `9:16` `4:3` `3:4` `3:2` `2:3` `2:1` `1:2` · `n ≤ 10` |
| `gpt-image-2`, `gpt-image-2-2026-04-21` | constrained pixel range | edges divisible by 16 and ≤3840, ratio `1:3`–`3:1`, 655,360–8,294,400 pixels · `n ≤ 10` |
| `gpt-image-1.5`, `gpt-image-1`, `gpt-image-1-mini` | fixed pixel sizes | `1024x1024` `1536x1024` `1024x1536` (`auto` is recorded but never sent) · `n ≤ 10` |
| `image-01` | ratio enum | `1:1` `16:9` `4:3` `3:2` `2:3` `3:4` `9:16` `21:9` · `n ≤ 9` · prompt ≤1500 characters |

`MODEL_ASPECTS` stores a `ModelCapability` for each row rather than a set.
Exactly one of `ratio_enum`, `pixel_sizes`, or `pixel_range` is populated;
`n_max` and optional `prompt_max_chars` travel with it. For OpenAI models,
`pixel_size(model, aspect)` translates a ratio to `WIDTHxHEIGHT`: the 1.x line
uses its fixed lookup, while `gpt-image-2` searches the constrained range.

### Not every listed model can render a dense spec

The table above is about *frames*. It says nothing about whether a model can
letter forty lines of authored copy correctly, and they differ sharply. Measured
across the integration testbed on 2026-08-16, one candidate per recipe:

| Model | Dense spec copy |
|---|---|
| `grok-imagine-image-2.0`, `grok-imagine-image-quality`, `grok-imagine-image` | reliable — 16 of 17 rows letter-perfect |
| `gpt-image-2`, `gpt-image-2-2026-04-21` | reliable |
| `gpt-image-1.5` | reliable |
| **`gpt-image-1`, `gpt-image-1-mini`** | **not suitable** |

The 1.0 tier fails structurally rather than cosmetically: whole sections vanish,
headings desync from the bodies beneath them, and panels duplicate. One row
rendered `01 - THE MESH` above section 01's content and dropped section 02
entirely; another printed `MagicONS` for `MagicDNS` and lost `04 - INGRESS`.
The frames were exact and `lith-run --strict` exited 0 for every one of them —
this is a copy-fidelity property, and no exit code detects it.

Use `gpt-image-1` and `gpt-image-1-mini` for a title-and-subtitle poster, or not
at all. For anything with sections, prefer `gpt-image-2`, `gpt-image-1.5`, or
the Grok line.

When a clamp happens, `lith-generate` prints `warning: ...` on stderr and sets
`aspect_note` in the envelope; `lith-run` prints it as a `[warn]` line.
`lith-call` prints the same warnings on stderr and carries `aspect_note`,
`copy_note` and `limit_notes` in its `--emit-json` payload, including under
`--check` and `--dry-run`.
`lith-run` also compares the *published* image's real dimensions against the
request and warns when they differ by more than 2%, which catches a provider
that ignored the field entirely.

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
checklist. No code reads them. They describe the sparse families (A, B, C, E,
F, G); a spec-driven family carrying `{spec}` and `{layout}` deliberately
overrides `max_words_in_image` and `always_one_idea_per_image`, since a dense
poster is many ideas and a hundred-odd words on purpose.

Pass an alternate file with `load_styles(path)`; the CLIs always use the
bundled copy.

---

## Output paths

The filename derives from `output_path(dir, family_key, headline, ext)`:

| File | Pattern | Example |
|---|---|---|
| Published image | `{family_key}_{slug(headline)}{ext}` | `outputs/B_brutalist_32_langs.jpg` |

The directory is `--output-dir` for `lith-run`, defaulting to the recipe's
sibling `outputs/`; `lith-generate` derives the same directory from `--recipe`,
and falls back to `./outputs` in flag mode where there is no recipe to anchor to. `lith-run` sniffs `ext` from the image bytes —
`.jpg`, `.png`, or `.webp`. `lith-generate` has no bytes yet, so a path it
derives is a bare stem and both commands print it the same way, as
`{stem}.<jpg|png|webp>`. An explicit `--out` is recorded verbatim instead. The
file is overwritten without prompting when a recipe is re-run.

`outputs/B_brutalist_32_langs_raw.jpg` is a committed reference artifact — real
Grok output for `recipes/live_test_recipe.json` — used by the tutorial and the
smoke test.

---

## Tests

```bash
uv run pytest
```

The suite covers prompt rendering, layout and aspect resolution, all three
CLIs, provider request/response fixtures, credential tiers, the brief expander,
and an end-to-end smoke test. Provider adapter tests are offline. The smoke test
skips with a clear message when the reference artifact in `outputs/` is absent.

---

## Status

| Component | State |
|---|---|
| Prompt rendering from `styles.json` | done |
| Recipe loader and dry-run driver | done |
| Validate-and-publish driver | done |
| Spec-driven poster copy (`{spec}` / `{layout}`) | done, all seven families |
| Layout vocabulary (15 arrangements) | done |
| Aspect resolution and per-model clamping | done |
| Published-image aspect check | done |
| Direct xAI/OpenAI/MiniMax provider layer | done — `lith-call` / `lith.call` |
| Credential inspection and request dry-run | done |
| Topic expansion (`expand_brief`) | done, library only — no CLI |
| Hermes `SKILL.md` wrapper | done, shipped in `skills/`; [installed manually](#install-the-hermes-skill) |
| Candidate scoring | not built |
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
| [About layouts](docs/explanation-layouts.md) | Explanation | Choosing an arrangement, or understanding the one lith derived |
| [About output styles](docs/explanation-output-styles.md) | Explanation | Choosing a family, and how one spec renders seven ways |
| [About the design language](docs/explanation-design-language.md) | Explanation | The palette, typography and composition rules underneath |
| [`skills/lith/SKILL.md`](skills/lith/SKILL.md) | Agent instructions | Checking what a Hermes session will do on your behalf |
| This README | Reference | Looking up a flag, a field, or a signature |

MIT licensed. See [LICENSE](LICENSE).
