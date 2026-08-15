# Python API and implementation reference

Complete reference for the `lith` package, version 0.1.0 — every public name,
every module, and the internals both console scripts are built from.

For flags and file formats, see [README → CLI reference](../README.md#cli-reference)
and [README → Recipe format](../README.md#recipe-format). For why the package
is shaped this way, see [About the pipeline](explanation-pipeline.md).

Conventions used below: **Raises** lists exceptions the function raises
directly or lets propagate unchanged. Paths accept `str` or `pathlib.Path`
wherever a signature says `path`.

---

## Contents

- [Package layout](#package-layout)
- [`lith` — public API](#lith--public-api)
- [`lith.render`](#lithrender)
- [`lith.recipe`](#lithrecipe)
- [`lith.styles`](#lithstyles)
- [`lith.paths`](#lithpaths)
- [`lith.typography`](#lithtypography)
- [`lith.expand`](#lithexpand)
- [`lith.overlay_text`](#lithoverlay_text)
- [`lith.cli.generate`](#lithcligenerate)
- [`lith.cli.run`](#lithclirun)
- [Exception summary](#exception-summary)
- [Side effects and determinism](#side-effects-and-determinism)

---

## Package layout

```
src/lith/
├── __init__.py          public API — re-exports seven names
├── render.py            prompt-template substitution
├── recipe.py            Recipe dataclass, family keys, recipe loading
├── styles.py            styles.json access
├── paths.py             slug and output-path derivation
├── typography.py        overlay_text.py subprocess wrapper
├── expand.py            LLM-backed topic expansion
├── overlay_text.py      ImageMagick overlay (script, not imported)
├── data/styles.json     the seven style families
└── cli/
    ├── generate.py      lith-generate entry point
    └── run.py           lith-run entry point
```

Internal dependency direction, no cycles:

```
recipe  ←  styles  ←  render
   ↑         ↑          ↑
   └─────────┴──────────┴──  __init__  ←  cli.generate, cli.run
paths, typography, expand           (leaves; depend on nothing in-package)
```

`overlay_text.py` is bundled as package data and executed as a subprocess by
`typography.py`. It is never imported, and it imports nothing from `lith`.

Runtime dependencies: none beyond the standard library. `overlay_typography`
requires the `magick` binary at call time; nothing else touches the network or
an external process.

---

## `lith` — public API

`__init__.py` re-exports seven names. `__all__` lists exactly these.

| Name | Kind | Defined in |
|---|---|---|
| [`render_prompt`](#render_prompt) | function | `lith.render` |
| [`load_recipe`](#load_recipe) | function | `lith.recipe` |
| [`overlay_typography`](#overlay_typography) | function | `lith.typography` |
| [`expand_brief`](#expand_brief) | function | `lith.expand` |
| [`parse_brief_response`](#parse_brief_response) | function | `lith.expand` |
| [`output_path`](#output_path) | function | `lith.paths` |
| [`slug`](#slug) | function | `lith.paths` |

```python
from lith import load_recipe, render_prompt, overlay_typography
```

Names not in `__all__` — `Recipe`, `FAMILY_KEYS`, `load_styles`, `get_family`,
and the module constants — are importable from their defining modules and are
used by both console scripts.

---

## `lith.render`

### `render_prompt`

```python
render_prompt(
    style: dict[str, Any] | Recipe,
    brief: dict[str, Any] | None = None,
) -> dict[str, str]
```

Substitutes brief values into a family's `prompt_template`.

Two calling forms:

| Form | Behavior |
|---|---|
| `render_prompt(recipe)` | Resolves the family from the bundled `styles.json` using `recipe.style`, and uses `recipe.brief`. |
| `render_prompt(style_mapping, brief_mapping)` | Uses the supplied mapping as the family definition. No file is read. |

**Returns** a `dict[str, str]` with exactly four keys:

| Key | Source |
|---|---|
| `prompt` | `style["prompt_template"]` with slots substituted |
| `negative_prompt` | `style.get("negative_prompt", "")`, coerced to `str` |
| `aspect_ratio` | `brief["aspect"]`, else `style.get("default_aspect")`, else `"16:9"` |
| `style` | `style["name"]`, coerced to `str` |

A falsy `brief["aspect"]` — `None`, `""` — falls through to the family default.

**Slot substitution.** The template is formatted with exactly five keyword
arguments, regardless of which the template uses:

| Slot | Value | Fallback |
|---|---|---|
| `{headline}` | `brief["headline"]` | `"NEW"` |
| `{icon}` | `brief["icon"]` | `"gear"` |
| `{volume}` | `brief["volume"]` | `"1"` |
| `{base_color}` | `style["palette"]["background"]` | `"#000000"` |
| `{accent}` | `style["palette"]["accent"]` | `"#00E5FF"` |

Because every slot has a fallback, an empty brief renders successfully against
any bundled family:

```python
>>> render_prompt(get_family(load_styles(), "B"), {})["aspect_ratio"]
'16:9'
```

**Raises**

| Exception | Condition |
|---|---|
| `KeyError` | The template references a slot outside the five above. Deliberate — a silently dropped slot is a silently drifted style. |
| `KeyError` | `style` has no `prompt_template` or no `name`. |
| `TypeError` | `brief` is supplied alongside a `Recipe` (`"brief must be omitted when rendering a Recipe"`). |
| `TypeError` | `style` is a mapping and `brief` is `None` (`"brief is required when style is a mapping"`). |

A custom family may use any subset of the five slots; a sixth slot raises:

```python
>>> render_prompt({"name": "x", "prompt_template": "{nope}"}, {})
KeyError: 'nope'
```

### `_palette_value`

```python
_palette_value(field: Any, default: str) -> str
```

Private. Resolves one palette field to a string for template insertion.

| Input | Result |
|---|---|
| `list`, non-empty | Elements joined with `" | "` — `["#a", "#b"]` → `"#a | #b"` |
| `list`, empty | `default` |
| `None` or `""` | `default` |
| anything else | the value unchanged |

The join, rather than taking the first element, is what lets `A_sticker` offer
four accents to the model in one prompt.

---

## `lith.recipe`

### `FAMILY_KEYS`

```python
FAMILY_KEYS: dict[str, str]
```

Maps a style letter to a family key in `styles.json`.

| Letter | Key | Letter | Key |
|---|---|---|---|
| `A` | `A_sticker` | `E` | `E_screenshot` |
| `B` | `B_brutalist` | `F` | `F_woodcut` |
| `C` | `C_patent` | `G` | `G_log` |
| `D` | `D_manga` | | |

### `REQUIRED_BRIEF_KEYS`

```python
REQUIRED_BRIEF_KEYS: set[str] = {"topic", "headline", "icon", "aspect"}
```

Enforced by `load_recipe`. Note that `volume` is optional and `topic` is
validated but never substituted into any template.

### `Recipe`

```python
@dataclass
class Recipe:
    name: str
    style: str
    brief: dict
    model: str
    n: int
    expected_output: str | None
    description: str | None
```

Plain dataclass — not frozen, no validation in `__init__`. Construct it
directly to bypass file loading and its checks.

**`family_key`** (property) → `str`. Returns `FAMILY_KEYS[self.style]`. Raises
`KeyError` if `style` is not one of `A`–`G`.

### `load_recipe`

```python
load_recipe(path: pathlib.Path | str) -> Recipe
```

Reads a JSON recipe file and returns a `Recipe`.

**Defaults applied** when a key is absent:

| Field | Default |
|---|---|
| `name` | `path.stem` |
| `model` | `"grok-imagine-image-quality"` |
| `n` | `4` |
| `expected_output` | `None` |
| `description` | `None` |
| `brief` | `{}` — then fails validation |

**Raises**

| Exception | Condition |
|---|---|
| `ValueError` | One or more of `REQUIRED_BRIEF_KEYS` is missing. Message names the file and lists the missing keys, sorted. |
| `KeyError` | `style` is absent from the file. |
| `json.JSONDecodeError` | The file is not valid JSON. |
| `FileNotFoundError` | `path` does not exist. |

**Not validated:** `style` is not checked against `FAMILY_KEYS`, `n` is not
checked to be a positive integer, `model` is not checked against the CLI's
choices, and `aspect` is not checked against the four supported ratios. A
recipe with `"style": "Z"` loads without error and raises `KeyError: 'Z'` later,
at `.family_key` or `get_family`.

```python
>>> r = load_recipe("recipes/live_test_recipe.json")
>>> r.family_key, r.model, r.n
('B_brutalist', 'grok-imagine-image-quality', 4)
```

---

## `lith.styles`

### `load_styles`

```python
load_styles(path: pathlib.Path | str | None = None) -> dict
```

Parses a styles file and returns it whole. With `path` as `None`, reads the
bundled `lith/data/styles.json` through `importlib.resources`, which works from
a zipped or relocated install. With a `path`, reads that file. Both are decoded
as UTF-8.

**Returns** the parsed document: `{"version", "description", "families", "rules"}`.
No schema validation is performed.

**Raises** `FileNotFoundError` for a missing explicit `path`;
`json.JSONDecodeError` for malformed JSON.

### `get_family`

```python
get_family(styles: dict, letter: str) -> dict
```

Returns `styles["families"][FAMILY_KEYS[letter]]`.

**Raises** `KeyError` — the letter if it is not `A`–`G`, or the family key if
the document lacks that family.

---

## `lith.paths`

### `slug`

```python
slug(text: str) -> str
```

Lowercases, replaces each run of non-alphanumeric characters with a single
underscore, and strips leading and trailing underscores.

| Input | Output |
|---|---|
| `"32 LANGS"` | `"32_langs"` |
| `"  A B--c  "` | `"a_b_c"` |
| `""` | `"untitled"` |
| `"!!!"` | `"untitled"` |

Non-ASCII alphanumerics are treated as separators: the pattern is
`[^a-z0-9]+`, applied after lowercasing. A headline of only non-ASCII
characters therefore yields `"untitled"`.

### `output_path`

```python
output_path(
    out_dir: pathlib.Path | str,
    family_key: str,
    headline: str,
    ext: str,
) -> pathlib.Path
```

Returns `out_dir / f"{family_key}_{slug(headline)}{ext}"`. Pure — creates no
directory and touches no file. `ext` is concatenated verbatim, so it must
include its leading dot, and callers pass suffixes such as `"_raw.jpg"` to
build the raw-image name.

```python
>>> output_path("/o", "B_brutalist", "32 LANGS", ".png")
PosixPath('/o/B_brutalist_32_langs.png')
```

---

## `lith.typography`

### `overlay_typography`

```python
overlay_typography(
    src: pathlib.Path,
    dst: pathlib.Path,
    lines: list[tuple[str, str]],
    font: pathlib.Path | None = None,
) -> pathlib.Path
```

Runs the bundled `overlay_text.py` as a subprocess to paint literal copy onto
`src`, writing `dst`. Each `lines` entry is a `(label, copy)` tuple; the script
renders the label bracketed as `[LABEL]`.

Creates `dst.parent` before invoking the subprocess. Returns `dst`.

Invoked as `[sys.executable, overlay_text.py, --input, src, --output, dst,
(--font, font)?, (--line, f"{label}={body}")...]` with `check=True`. Arguments
are passed as a list, never through a shell.

**Only `font` is forwarded.** Point size, mask rectangle, baseline, line height,
column offsets, and both colors stay at the script's defaults. To reach them,
invoke [`overlay_text.py`](#lithoverlay_text) directly.

**Raises**

| Exception | Condition |
|---|---|
| `FileNotFoundError` | `src` is not a file, or the bundled script is missing from the install. |
| `subprocess.CalledProcessError` | The script exits nonzero — missing `magick`, missing font, or a `magick` failure. |

An empty `lines` list produces no `--line` argument, and the script exits 2
because `--line` is required.

### `_OVERLAY_SCRIPT`

```python
_OVERLAY_SCRIPT: pathlib.Path
```

Private. Absolute path to `overlay_text.py`, resolved next to
`typography.py`. Existence is checked on each call rather than at import.

---

## `lith.expand`

### `DEFAULT_PROMPT`

```python
DEFAULT_PROMPT: str
```

The brief-expansion prompt template. Instructs the model to return a JSON
object with `topic`, `headline`, `icon`, `aspect`, and `mood`; to choose `icon`
from `{gear, lightning, globe, skull, brain, rocket, lock}`; to default to
style B; and to emit no prose outside the JSON block.

Contains a literal `{topic}` placeholder **and** a literal brace list, which is
why substitution uses `str.replace` rather than `str.format`.

### `expand_brief`

```python
expand_brief(
    topic: str,
    llm_cmd: list[str],
    prompt_template: str = DEFAULT_PROMPT,
    timeout: int = 60,
) -> dict
```

Renders `prompt_template` by replacing every `{topic}` with `topic`, runs
`llm_cmd` with that text on stdin, and parses stdout with
`parse_brief_response`.

`llm_cmd` is a subprocess argv list supplied by the caller — `lith` names no
model and holds no credentials. The command must read the prompt from stdin and
write a reply containing a JSON object to stdout. Run with `check=True`,
`text=True`, and `capture_output=True`; stderr is captured and discarded unless
the command fails.

**Returns** the parsed object as-is. Fields are not validated against
`REQUIRED_BRIEF_KEYS`, so the result is not guaranteed to satisfy a recipe.

**Raises**

| Exception | Condition |
|---|---|
| `subprocess.CalledProcessError` | `llm_cmd` exits nonzero. |
| `subprocess.TimeoutExpired` | `llm_cmd` exceeds `timeout` seconds. |
| `FileNotFoundError` | `llm_cmd[0]` is not on `$PATH`. |
| `ValueError` | stdout contains no decodable JSON object. |

### `parse_brief_response`

```python
parse_brief_response(text: str) -> dict
```

Returns the first decodable JSON object in `text`. Scans for each `{` and
attempts `json.JSONDecoder().raw_decode` at that index, returning the first
success. Trailing content after the object is ignored, so code fences,
preamble, and commentary are all tolerated:

```python
>>> parse_brief_response('prose\n```json\n{"a": 1}\n```\ntail')
{'a': 1}
>>> parse_brief_response('{bad} then {"b": 2}')
{'b': 2}
```

Because the scan is left-to-right and returns the first success, a valid object
nested inside an earlier one wins only if the outer object fails to decode.

**Raises** `ValueError` if no `{` yields a decodable object. The message
includes the first 200 characters of `text`.

---

## `lith.overlay_text`

A standalone script bundled as package data, executed via `sys.executable`. It
imports nothing from `lith` and is not importable as part of the public API.
Full flag table: [README → `overlay_text.py`](../README.md#overlay_textpy).

### `DEFAULT_FONT`

```python
DEFAULT_FONT = pathlib.Path("/System/Library/Fonts/Menlo.ttc")
```

macOS-specific. On other platforms every call must pass `--font`.

### `parse_line`

```python
parse_line(value: str) -> tuple[str, str]
```

Splits `"LABEL=copy"` on the first `=` and strips both halves. Copy may itself
contain `=`.

**Raises** `argparse.ArgumentTypeError` when `=` is absent, or when either half
is empty after stripping.

An identical `parse_line` exists in `lith.cli.run`; the two are independent
copies, each serving its own argument parser.

### `main`

```python
main() -> int
```

Builds and runs one `magick` invocation: fills `--mask` with black, then for
each line *i* draws `[LABEL]` at (`--x`, `--y` + *i* × `--line-height`) in
`--label-color` and the copy at (`--body-x`, same *y*) in `--body-color`.
Creates the output's parent directory. Prints the output path on success.

**Returns** `0` on success; `2` if `magick` is not on `$PATH`, the input is not
a file, or the font is not a file. Raises `subprocess.CalledProcessError` if
`magick` itself exits nonzero.

---

## `lith.cli.generate`

Entry point for `lith-generate`. Flags:
[README → `lith-generate`](../README.md#lith-generate).

### `build_brief`

```python
build_brief(args: argparse.Namespace) -> dict
```

Assembles a brief from flags: `topic`, `headline`, `icon`, and `aspect` from
`args`, plus a hard-coded `"volume": "1"`. The `--volume` flag does not exist,
so family C's volume is always `1` from the CLI; a recipe file can set it.

### `main`

```python
main() -> int
```

Resolves the brief from `--recipe` or from flags, renders the prompt, and
prints either a summary or a call envelope.

Precedence with `--recipe`: `n` and `model` come from the recipe, so `--n` and
`--model` are silently ignored. `--seed` and `--out` are read from flags in
both modes. When `--out` is absent, the output path is
`cwd/outputs/{family_key}_{slug(headline)}.png`, resolved at call time from
`pathlib.Path.cwd()`.

Without `--recipe`, `--topic`, `--style`, and `--headline` are each required;
a missing one triggers `parser.error`, which exits 2.

**Returns** `0`. Argparse errors exit 2 without returning.

---

## `lith.cli.run`

Entry point for `lith-run`. Flags: [README → `lith-run`](../README.md#lith-run).

### Module constants

| Constant | Value |
|---|---|
| `ALLOWED_SCHEMES` | `("http", "https")` |
| `DOWNLOAD_TIMEOUT` | `30` (seconds) |
| `DOWNLOAD_MAX_BYTES` | `26214400` (25 MiB) |
| `JPEG_MAGIC` | `b"\xff\xd8\xff"` |
| `PNG_MAGIC` | `b"\x89PNG\r\n\x1a\n"` |

### `_looks_like_image`

```python
_looks_like_image(body: bytes) -> bool
```

Private. True when `body` starts with `JPEG_MAGIC`, starts with `PNG_MAGIC`, or
starts with `b"RIFF"` with `b"WEBP"` at offset 8. Header inspection only — no
decode, no dimension check, no validation of anything past byte 12.

### `download`

```python
download(url: str, dst: pathlib.Path) -> pathlib.Path
```

Fetches an image over HTTP(S) into `dst`, applying five guards in order:

1. **Scheme and host.** A missing scheme or empty netloc raises
   `refusing to fetch non-URL`. A scheme outside `ALLOWED_SCHEMES` raises
   `refusing to fetch scheme`. Comparison is case-insensitive.
2. **Timeout.** `DOWNLOAD_TIMEOUT` on the `urlopen` call.
3. **Post-redirect scheme.** The final `response.url` scheme is re-checked, so
   an `http(s)` URL redirecting to `file:` is refused.
4. **Size ceiling.** Chunks are counted while streaming and the read aborts
   past `DOWNLOAD_MAX_BYTES`, before the body is assembled or written.
5. **Magic bytes.** `_looks_like_image` must pass. An HTML error page fails
   here rather than landing on disk as a `.jpg`.

Sends `User-Agent: lith/1.0`. Creates `dst.parent` and writes only after all
five guards pass. Returns `dst`.

**Raises** `ValueError` for any guard failure, plus `urllib.error.URLError` /
`HTTPError` / `socket.timeout` from the network layer.

```python
>>> download("file:///etc/hosts", dst)
ValueError: refusing to fetch scheme 'file'; allowed: ('http', 'https')
```

Not covered: DNS rebinding, redirect-count limits, and private-address
filtering — `urllib`'s defaults apply, and a redirect to an internal HTTP host
is permitted.

### `load_local`

```python
load_local(src: pathlib.Path, dst: pathlib.Path) -> pathlib.Path
```

Copies a local image into the pipeline's raw path. Reads `src` whole, applies
the same `_looks_like_image` check, creates `dst.parent`, and writes — unless
`src` and `dst` resolve to the same file, in which case the write is skipped.
Returns `dst`.

**Raises** `FileNotFoundError` if `src` is not a file; `ValueError` if the
magic-byte check fails.

### `parse_line`

Identical in behavior to [`lith.overlay_text.parse_line`](#parse_line).

### `main`

```python
main() -> int
```

Loads the recipe, renders the prompt, and derives both output paths. Branches
three ways:

| Branch | Effect |
|---|---|
| No image source | Prints recipe, family, style, aspect, model, `n`, prompt, and final output path. Writes nothing. |
| Image source, no `--line` | Ingests to the raw path, prints `[warn] no --line supplied`, reports the raw file as done. |
| Image source with `--line` | Ingests to the raw path, overlays, reports the final PNG as done. |

Raw path: `{output_dir}/{family_key}_{slug(headline)}_raw.jpg` — the `.jpg`
suffix is fixed regardless of the source format. Final path: the same stem with
`.png`. Both are overwritten without prompting.

`--image-url` and `--image-file` are a mutually exclusive argparse group.
Progress lines print with `flush=True`.

**Returns** `0` in all three branches. Argparse errors exit 2. Guard failures
from `download` or `load_local`, and a nonzero `magick`, propagate as
tracebacks.

---

## Exception summary

| Exception | Raised by | Trigger |
|---|---|---|
| `KeyError` | `render_prompt` | Template slot outside the supported five |
| `KeyError` | `load_recipe` | Missing `style` key |
| `KeyError` | `get_family`, `Recipe.family_key` | Style letter outside `A`–`G` |
| `TypeError` | `render_prompt` | `Recipe` with a brief, or mapping without one |
| `ValueError` | `load_recipe` | Missing required brief keys |
| `ValueError` | `parse_brief_response`, `expand_brief` | No decodable JSON object |
| `ValueError` | `download` | Bad scheme, bad redirect, oversize body, non-image bytes |
| `ValueError` | `load_local` | Non-image bytes |
| `FileNotFoundError` | `load_recipe`, `load_styles`, `load_local`, `overlay_typography` | Missing input file |
| `json.JSONDecodeError` | `load_recipe`, `load_styles` | Malformed JSON |
| `subprocess.CalledProcessError` | `overlay_typography`, `expand_brief` | Subprocess exits nonzero |
| `subprocess.TimeoutExpired` | `expand_brief` | Command exceeds `timeout` |
| `argparse.ArgumentTypeError` | `parse_line` | Malformed `LABEL=copy` |

No custom exception types are defined.

---

## Side effects and determinism

| Function | Filesystem | Network | Subprocess | Deterministic |
|---|---|---|---|---|
| `render_prompt` | — | — | — | yes |
| `slug`, `output_path` | — | — | — | yes |
| `load_recipe` | read | — | — | yes |
| `load_styles`, `get_family` | read | — | — | yes |
| `parse_brief_response` | — | — | — | yes |
| `overlay_typography` | read + write | — | `magick` | yes, given the same inputs |
| `expand_brief` | — | via `llm_cmd` | `llm_cmd` | no |
| `download` | write | yes | — | no |
| `load_local` | read + write | — | — | yes |

`render_prompt` is a pure function of its arguments plus the bundled
`styles.json`, so the same recipe yields the same prompt across runs and
machines. Randomness enters only through `expand_brief`'s model and whatever
generates the image between the two console scripts.

Output paths are derived, not unique: re-running a recipe overwrites the
previous artifacts.

---

## See also

- [README → CLI reference](../README.md#cli-reference) — the two console scripts
- [README → Recipe format](../README.md#recipe-format) — the JSON schema
- [About the pipeline](explanation-pipeline.md) — why the library stops where it does
- [Tutorial: your first announcement image](tutorial-first-image.md) — the API in use
