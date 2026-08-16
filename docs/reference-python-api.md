# Python API and implementation reference

Complete reference for the `lith` package, version 0.1.0 — every public name,
every module, and the internals its three console scripts are built from.

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
- [`lith.layout`](#lithlayout)
- [`lith.aspect`](#lithaspect)
- [`lith.call`](#lithcall)
- [`lith.recipe`](#lithrecipe)
- [`lith.styles`](#lithstyles)
- [`lith.paths`](#lithpaths)
- [`lith.expand`](#lithexpand)
- [`lith.imagebytes`](#lithimagebytes)
- [`lith.cli.generate`](#lithcligenerate)
- [`lith.cli.call`](#lithclicall)
- [`lith.cli.run`](#lithclirun)
- [Exception summary](#exception-summary)
- [Side effects and determinism](#side-effects-and-determinism)

---

## Package layout

```
src/lith/
├── __init__.py          public API — re-exports six names
├── render.py            prompt-template substitution, spec and layout blocks
├── aspect.py            capability records, aspect resolution, pixel sizes
├── layout.py            zone notes and panel arrangements
├── recipe.py            Recipe dataclass, family keys, recipe loading
├── styles.py            styles.json access
├── paths.py             slug and output-path derivation
├── expand.py            LLM-backed topic expansion
├── imagebytes.py        image download, magic-byte sniffing, dimensions
├── call/
│   ├── __init__.py      uniform request/results and provider dispatcher
│   ├── capability.py    model-to-provider routing
│   ├── creds.py         four-tier credential resolution
│   ├── http.py          urllib JSON transport and typed provider errors
│   ├── xai.py           xAI generations adapter
│   ├── openai.py        OpenAI generations adapter
│   └── minimax.py       MiniMax text-to-image adapter
├── data/styles.json     the seven style families
└── cli/
    ├── generate.py      lith-generate entry point
    ├── call.py          lith-call entry point
    └── run.py           lith-run entry point
```

The prompt side remains pure and points downward only:

```
recipe  ←  styles
   ↑          ↑
   └──────────┴──  render  ←  __init__  ←  cli.generate
             ↗   ↖
        aspect     layout        (pure; depend on nothing in-package)

paths, expand                    (leaves; depend on nothing in-package)

aspect, imagebytes  ←  call adapters  ←  lith.call dispatcher  ←  cli.call
imagebytes, render, paths                                      ←  cli.run
```

`render` is the only module that composes others: it resolves the frame through
`aspect`, describes the zones through `layout`, and serializes the copy block
itself. The provider layer may import pure modules such as `aspect` and
`imagebytes`; pure modules never import `lith.call` or `lith.cli`.

Runtime dependencies: none beyond the standard library, and no external
binaries. `expand_brief` starts only the `llm_cmd` a caller supplies. Network
access is isolated to `imagebytes.download` and the provider adapters' shared
`urllib` JSON transport.

---

## `lith` — public API

`__init__.py` re-exports six names. `__all__` lists exactly these.

| Name | Kind | Defined in |
|---|---|---|
| [`render_prompt`](#render_prompt) | function | `lith.render` |
| [`load_recipe`](#load_recipe) | function | `lith.recipe` |
| [`expand_brief`](#expand_brief) | function | `lith.expand` |
| [`parse_brief_response`](#parse_brief_response) | function | `lith.expand` |
| [`output_path`](#output_path) | function | `lith.paths` |
| [`slug`](#slug) | function | `lith.paths` |

```python
from lith import load_recipe, render_prompt
```

Names not in `__all__` — `Recipe`, `FAMILY_KEYS`, `load_styles`, `get_family`,
`format_spec`, `format_layout`, and the module constants — are importable from
their defining modules and are used by the console scripts.

---

## `lith.render`

### `render_prompt`

```python
render_prompt(
    style: dict[str, Any] | Recipe,
    brief: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, str]
```

Substitutes brief values into a family's `prompt_template`.

Two calling forms:

| Form | Behavior |
|---|---|
| `render_prompt(recipe)` | Resolves the family from the bundled `styles.json` using `recipe.style`, and uses `recipe.brief`. |
| `render_prompt(style_mapping, brief_mapping)` | Uses the supplied mapping as the family definition. No file is read. |

**Returns** a `dict` with exactly six keys:

| Key | Source |
|---|---|
| `prompt` | `style["prompt_template"]` with slots substituted |
| `negative_prompt` | `style.get("negative_prompt", "")`, coerced to `str` |
| `aspect_ratio` | [`resolve_aspect`](#resolve_aspect) |
| `style` | `style["name"]`, coerced to `str` |
| `aspect_note` | `str` when the model forced a substitution, else `None` |
| `copy_note` | [`copy_note`](#copy_note) — `str` when the copy block is too thin, else `None` |

`model` selects the capability set the ratio is clamped against. Rendering a
`Recipe` takes it from `recipe.model` unless overridden. With no model, no
clamping happens.

**Slot substitution.** The template is formatted with exactly seven keyword
arguments, regardless of which the template uses:

| Slot | Value | Fallback |
|---|---|---|
| `{headline}` | `brief["headline"]` | `"NEW"` |
| `{icon}` | `brief["icon"]` | `"gear"` |
| `{volume}` | `brief["volume"]` | `"1"` |
| `{base_color}` | `brief["base_color"]`, else `style["palette"]["background"]` | `"#000000"` |
| `{accent}` | `brief["accent"]`, else `style["palette"]["accent"]` | `"#00E5FF"` |
| `{spec}` | [`format_spec(brief)`](#format_spec) | `""` for an empty brief |
| `{layout}` | [`format_layout(brief, landscape)`](#format_layout) | the title zone alone |

Both palette slots take the brief's value first. `D_manga` is the family this
matters for: its `palette.background` lists three colors.

Because every slot has a fallback, an empty brief renders successfully against
any bundled family:

```python
>>> render_prompt(get_family(load_styles(), "B"), {})["aspect_ratio"]
'16:9'
```

**Raises**

| Exception | Condition |
|---|---|
| `KeyError` | The template references a slot outside the seven above. |
| `KeyError` | `style` has no `prompt_template` or no `name`. |
| `TypeError` | `brief` is supplied alongside a `Recipe` (`"brief must be omitted when rendering a Recipe"`). |
| `TypeError` | `style` is a mapping and `brief` is `None` (`"brief is required when style is a mapping"`). |
| `ValueError` | `format_spec` hits a section with no `heading`. |

A custom family may use any subset of the seven slots; an eighth slot raises:

```python
>>> render_prompt({"name": "x", "prompt_template": "{nope}"}, {})
KeyError: 'nope'
```

### `format_spec`

```python
format_spec(brief: dict[str, Any]) -> str
```

Serializes the brief's copy fields into the literal block substituted at
`{spec}`. Every line it emits is text the model is instructed to reproduce
character for character.

Emitted in this fixed order, each part omitted when its field is absent. The
block is purely literal text — `diagram` is a description, so it lives in
[`format_layout`](#format_layout) among the instructions instead:

| Part | Source | Form |
|---|---|---|
| Title | `brief["title"]`, else `brief["headline"]` | `TITLE: <text>` |
| Subtitle | `brief["subtitle"]` | `SUBTITLE: <text>` |
| Sections | `brief["sections"]`, in order | `SECTION <n> HEADING: <heading>` then one `    - <line>` per entry in `lines` |
| Footer | `brief["footer"]` | `FOOTER: <text>` |

Parts are joined with `\n`. Section numbering is 1-based and follows list
order. A section with an empty or absent `lines` yields its heading alone.

**Returns** `""` for a brief with none of these fields. A brief carrying only
`headline` degrades to a single `TITLE:` line, which is what every pre-spec
recipe produces.

**Raises** `ValueError` when a section has no `heading`, naming its 1-based
index and including its `repr`.

### `copy_note`

```python
copy_note(spec: str, prompt: str) -> str | None
```

Warns when the copy block is too thin relative to the instructions around it.
Returns `None` when `len(spec) * 20 >= len(prompt) - len(spec)`, otherwise a
sentence naming both character counts.

The ratio matters rather than the raw length, because the template is a fixed
cost — palette, mood, layout preamble — that scales per family while only the
spec block varies. A brief with no `sections` renders a copy block of roughly
sixteen characters against fifteen hundred of instructions, and at that ratio
the model starts lettering the instructions: real output has printed palette
hex codes as panel headings and a font name as body copy.

This never blocks rendering. A title-only poster is a legitimate request, and
[`format_layout`](#format_layout) already emits only the zones the brief has
copy for. The note exists so the caller learns before the call rather than
after, and it reaches them three ways: on stderr from `lith-generate`, as a
`[warn]` line from `lith-run`, and as the envelope's `copy_note` field.

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

The join preserves every element rather than taking the first; `A_sticker`
is the family that relies on it, offering four accents in one prompt.

---

---

## `lith.layout`

### `ARRANGEMENTS`

```python
ARRANGEMENTS: dict[str, str]
```

Maps a `layout` key to the phrase describing how section panels sit in the
frame: `stack`, `two-column`, `three-column`, `grid-2x2`, `grid-2x3`,
`grid-3x2`, `grid-3x3`, `hero`, `sidebar`, `timeline`, `radial`, `masonry`,
`zigzag`, `split`, `diagonal`.

### `DIAGRAM_POSITIONS`

```python
DIAGRAM_POSITIONS: dict[str, str]
```

`below` (default), `above`, `beside`, `center`. A `radial` arrangement forces
`center`.

### `_auto_arrangement`

```python
_auto_arrangement(count: int, landscape: bool) -> str
```

Private. The derived arrangement for a panel count and orientation, used by
[`resolve_arrangement`](#resolve_arrangement) when `brief["layout"]` is absent.
Column counts cap at two in portrait.

### `resolve_arrangement`

```python
resolve_arrangement(
    brief: dict[str, Any], count: int, landscape: bool = False
) -> str
```

`brief["layout"]` when set, else derived from `count` and orientation. Raises
`ValueError` naming every valid key when `brief["layout"]` is unknown.

Column counts cap at two in portrait. Derived values:

| `count` | portrait | landscape |
|---|---|---|
| 1 | `stack` | `stack` |
| 2 | `two-column` | `two-column` |
| 3 | `hero` | `three-column` |
| 4 | `grid-2x2` | `grid-2x2` |
| 5 | `hero` | `hero` |
| 6 | `grid-2x3` | `grid-3x2` |
| 7–9 | `two-column` | `grid-3x3` |
| 10+ | `two-column` | `two-column` |

### `format_layout`

```python
format_layout(brief: dict[str, Any]) -> str
```

Describes the zones the brief actually has copy for, substituted at
`{layout}`. Zones are numbered `(1)`, `(2)`, … and joined with `\n`.

The wording is deliberately aesthetic-neutral — it names structure, counts and
sizes only. Each family's `prompt_template` says how those zones are drawn, so
one function serves all seven.

```python
format_layout(brief: dict[str, Any], landscape: bool = False) -> str
```

| Zone | Emitted when | Notes |
|---|---|---|
| Title | always | Sized `12-15%` of frame height with sections present, `30-40%` and "dominating the composition" without. Gains a subtitle clause when `subtitle` is set. |
| Section panels | `sections` is non-empty | Arranged per [`resolve_arrangement`](#resolve_arrangement). Names the panel count and the longest section's line count, and forbids padding a short panel. |
| Drawing | `diagram` is set | Placed per `diagram_position`. Carries the description and the order to letter only the labels it names. |
| Footer | `footer` is set | A rule with the footer text beneath. |

Every note is lowercase prose. Nothing here may read like a heading: the block
sits in the same prompt as the verbatim-copy order, and ALL-CAPS zone labels
were lettered into real output as visible headings before this was fixed.

**Raises** `ValueError` for an unknown `layout` or `diagram_position`.

Pure — no file or network access, and deterministic for a given brief. Why the
zones track the spec instead of being a fixed skeleton:
[About the pipeline → Why the copy is specified](explanation-pipeline.md#why-the-copy-is-specified-never-improvised).


## `lith.aspect`

### `MODEL_ASPECTS`

```python
MODEL_ASPECTS: dict[str, ModelCapability]
```

Every known model carries one aspect-capability variant plus its request
limits. A model absent from the table is unconstrained by the prompt renderer;
the call dispatcher still rejects unknown ids.

| Model | Aspect variant | Other limits |
|---|---|---|
| `grok-imagine-image-2.0` | 14-value `ratio_enum`, including `auto` | `n_max=10` |
| `grok-imagine-image-quality`, `grok-imagine-image` | 9-value `ratio_enum` | `n_max=10` |
| `gpt-image-2`, `gpt-image-2-2026-04-21` | `pixel_range`: edges ÷16 and ≤3840; ratio `1:3`–`3:1`; 655,360–8,294,400 pixels; `allows_auto=True` | `n_max=10` |
| `gpt-image-1.5`, `gpt-image-1`, `gpt-image-1-mini` | `pixel_sizes=("1024x1024", "1536x1024", "1024x1536", "auto")` | `n_max=10` |
| `image-01` | 8-value `ratio_enum` | `n_max=9`, `prompt_max_chars=1500` |

The xAI 2.0 enum is `1:1`, `3:4`, `4:3`, `9:16`, `16:9`, `2:3`, `3:2`,
`9:19.5`, `19.5:9`, `9:20`, `20:9`, `1:2`, `2:1`, `auto`. The MiniMax enum
is `1:1`, `16:9`, `4:3`, `3:2`, `2:3`, `3:4`, `9:16`, `21:9`. Adapters never
send `auto`; lith resolves a concrete frame.

### `PixelSizeRange`

```python
@dataclass(frozen=True)
class PixelSizeRange:
    edge_multiple: int
    min_aspect: float
    max_aspect: float
    min_pixels: int
    max_pixels: int
    max_edge: int
    allows_auto: bool = False
```

The interacting constraints for a model that accepts arbitrary pixel sizes.
It is data only; [`pixel_size`](#pixel_size) performs the search.

### `ModelCapability`

```python
@dataclass(frozen=True)
class ModelCapability:
    n_max: int
    prompt_max_chars: int | None = None
    ratio_enum: frozenset[str] | None = None
    pixel_sizes: tuple[str, ...] | None = None
    pixel_range: PixelSizeRange | None = None
```

Exactly one of `ratio_enum`, `pixel_sizes`, and `pixel_range` must be non-null;
construction otherwise raises `ValueError`. `n_max` and a non-null
`prompt_max_chars` must be positive. `aspect in capability` checks a ratio enum,
reduces fixed pixel sizes to ratios, or tests the range's aspect bounds.


### `ratio`

```python
ratio(aspect: str) -> float | None
```

Width over height. `None` for anything that is not `N:M` with both terms
nonzero — `"auto"`, `"0:0"`, a non-string.

### `supported_by`

```python
supported_by(model: str | None) -> ModelCapability | None
```

`MODEL_ASPECTS[model]`, or `None` for an unknown or absent model.

### `unsupported_aspect`

```python
unsupported_aspect(model: str, aspect: str) -> str | None
```

A message naming the supported set when `model` cannot produce `aspect`, else
`None`. A constrained pixel range admits every parseable ratio inside its
bounds rather than only a finite list of examples.

### `nearest_supported`

```python
nearest_supported(model: str | None, aspect: str) -> str
```

The supported ratio closest to `aspect` by width/height, so a portrait request
lands on a portrait ratio. Returns `aspect` unchanged when the model is
unconstrained, already supports it, or when `aspect` is unparseable. A ratio
inside a constrained range is already supported and passes through unchanged.

### `pixel_size`

```python
pixel_size(model: str, aspect: str) -> str
```

Translates an OpenAI model and concrete ratio to `"WIDTHxHEIGHT"`.

- The GPT Image 1.x models visibly clamp through `nearest_supported`, then map
  to one of their three fixed sizes.
- `gpt-image-2` and its snapshot search sizes whose edges are divisible by 16,
  whose ratio and pixel area are in range, and whose maximum edge is 3840. The
  most accurate ratio wins; equal-error candidates prefer smaller area.

Pure and deterministic. Raises `ValueError` for an unknown model, a ratio-enum
model, an invalid or out-of-range aspect, or an aspect no legal pixel size can
represent.

```python
>>> pixel_size("gpt-image-1", "16:9")
'1536x1024'
>>> pixel_size("gpt-image-2", "20:9")
'1280x576'
```

### `request_limit_notes`

```python
request_limit_notes(model: str, n: int, prompt: str) -> list[str]
```

Returns notes when `n` exceeds the model's `n_max` or `len(prompt)` exceeds its
`prompt_max_chars`. Unknown models return an empty list. This is advisory in
`lith-generate`; provider adapters still validate before network access.

### `content_aspect`

```python
content_aspect(brief: dict[str, Any], style: dict[str, Any]) -> str | None
```

The ratio the brief's content shape calls for, or `None`.

| Condition | Result |
|---|---|
| `style["prompt_template"]` has no `{spec}` | `None` — a custom family that opts out |
| 3 or more `sections` | `"2:3"` |
| 1–2 `sections` | `"1:1"` |
| no `sections` | `None` |

### `resolve_aspect`

```python
resolve_aspect(
    brief: dict[str, Any],
    style: dict[str, Any],
    model: str | None = None,
) -> tuple[str, str | None]
```

Resolves the final ratio and a note about any substitution. Precedence:

1. `brief["aspect"]` — set by you, or by `expand_brief` from the topic
2. [`content_aspect`](#content_aspect) — spec-carrying families only
3. `style["default_aspect"]`
4. `FALLBACK_ASPECT` (`"16:9"`)

Whatever the first four choose is then clamped by
[`nearest_supported`](#nearest_supported). The note is `None` unless step 4
changed the answer.

All functions in this module are pure — no file, network, or subprocess access.

---

## `lith.call`

Provider-independent request and result types plus the model dispatcher. Importing
the package performs no credential lookup and no network access; the selected
adapter is imported lazily by `generate`.

### `ImageRequest`

```python
@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    model: str
    aspect: str
    n: int = 1
    seed: int | None = None
    resolution: str | None = None
    quality: str | None = None
    background: str | None = None
    negative_prompt: str | None = None
```

`aspect` is lith's resolved concrete `W:H` value. Adapters send only fields
their provider accepts. A supplied field that cannot be sent is recorded in
[`CallResult.unsupported`](#callresult); it is never appended or prepended to
`prompt`.

### `Candidate`

```python
@dataclass
class Candidate:
    index: int
    data: bytes
    mime: str
    dimensions: tuple[int, int] | None
```

Provider base64 is decoded before return, so every candidate holds bytes.
`dimensions` comes from PNG or JPEG headers and is `None` when the format's
dimensions cannot be read.

### `CallResult`

```python
@dataclass
class CallResult:
    candidates: list[Candidate]
    model_reported: str | None
    aspect_reported: str | None
    revised_prompt: str | None
    unsupported: dict[str, str]
    cost: str | None
    raw: dict
```

`model_reported`, `aspect_reported`, and `revised_prompt` surface provider
evidence when it exists. A successful explicit xAI/OpenAI request falls back to
the requested model id when the response omits a top-level model. Aspect does
not receive that fallback: candidate dimensions are the evidence that a frame
was honored. `cost` passes through xAI's `cost_in_usd_ticks` as text; lith does
not estimate costs for any provider. `raw` is the provider response object.

### `generate`

```python
generate(
    request: ImageRequest,
    *,
    credential=None,
    **provider_options,
) -> CallResult
```

Routes by exact model id and calls the corresponding adapter. `credential` may
be an already resolved [`Credential`](#credentials); when omitted, the adapter
resolves one itself. Unknown ids raise `ValueError` before any adapter import or
network access. Provider-specific keyword options are forwarded unchanged to
the selected adapter.

| Provider | Models | Translation |
|---|---|---|
| xAI | `grok-imagine-image-2.0`, `grok-imagine-image-quality`, `grok-imagine-image` | Sends concrete `aspect_ratio`, optional `resolution`, `n`, and explicit `response_format=b64_json`. |
| OpenAI | the five `gpt-image-*` ids in `MODEL_ASPECTS` | Sends [`pixel_size`](#pixel_size) as `size`, plus optional quality/background. GPT Image returns `b64_json` without a `response_format` request field. |
| MiniMax | `image-01` | Sends an enum `aspect_ratio` or explicit `width`/`height`, optional seed, `prompt_optimizer=false`, and `response_format=base64`. |

OpenAI-only controls stay off the uniform dataclass and are keyword arguments
on `lith.call.openai.build_request` / `generate`:

```python
generate(
    request,
    *,
    credential=None,
    output_format: str = "png",
    output_compression: int = 100,
    moderation: str = "auto",
) -> CallResult
```

Compression is emitted only for JPEG or WebP. The top-level dispatcher exposes
these provider-specific controls through `**provider_options`, so callers may
use either `lith.call.generate(request, output_format="webp", ...)` or the
OpenAI adapter directly.

xAI's default response format is inline `b64_json`. Passing `storage_options`
through the dispatcher requests URL delivery instead:

```python
generate(
    request,
    storage_options={
        "filename": "candidate.jpg",
        "expires_after": 3600,
        "public_url": True,
    },
)
```

The adapter checks only that the provider-required `filename` is present; xAI
validates `expires_after`, `public_url`, and future provider options. The adapter
accepts the public URL under `file_output.public_url` or the candidate's
ordinary `url`, fetches it under lith's download guards, and still returns image
bytes in `Candidate.data`. The CLI does not expose this provider-specific option.

MiniMax enforces its 1500-character prompt cap before credential resolution or
network access and raises `PromptTooLong`, an `InvalidRequest` subclass, naming
the measured length, cap, and backlog §3.1. Every current integration prompt is
over that cap.

### `provider_for_model`

```python
provider_for_model(model: str) -> str
```

Defined in `lith.call.capability`. Maps a model id to the adapter name that
serves it — `"xai"`, `"openai"`, or `"minimax"` — from the `MODEL_PROVIDERS`
table. [`generate`](#generate) uses it to select which adapter module to import.

The table's keys are exactly the keys of
[`aspect.MODEL_ASPECTS`](#model_aspects): a model that can be routed has a
capability record, and a model with a capability record can be routed.

**Raises** `ValueError` for an unknown id, listing every supported model. There
is no default provider and no inference from the id's shape.

### Credentials

```python
resolve_credential(
    provider: str,
    *,
    recipe_path=None,
    cwd=None,
    environ=None,
    home=None,
) -> Credential
```

Searches shell → recipe repository `.env` → `~/.hermes/.env` →
`~/.hermes/auth.json`; the first usable tier wins. The environment names are
exactly `XAI_API_KEY`, `OPENAI_API_KEY`, and `MINIMAX_API_KEY`. Tier 4 accepts
only OAuth entries whose `base_url` matches the provider image API. `Credential`
holds `provider`, a repr-hidden `secret`, `tier`, `source`, `auth_type`, and
optional OpenAI organization/project ids; `fingerprint` is an eight-character
hash for inspection.

Raises `MissingCredential` after all four tiers, with every searched location
in the message, or `CredentialFileError` when an existing credential file
cannot be read or parsed. Credential resolution never writes a file.

### Provider errors

`lith.call.http` defines this hierarchy:

```text
ProviderError
├── AuthError
├── RateLimited
├── ContentRejected
└── InvalidRequest
```

The standard-library JSON transport retries HTTP 429 and 5xx once, redacts
authorization values from rendered errors, and maps HTTP/provider payloads to
those types. MiniMax's `base_resp.status_code` is checked even inside HTTP 200.
An OAuth-sourced xAI 401 becomes `token expired — let Hermes refresh it`; lith
never refreshes or writes Hermes credentials.

### Provider adapters

Three modules, one per provider, each exposing the same three names.
[`generate`](#generate) imports the one
[`provider_for_model`](#provider_for_model) selects.

| Module | Endpoint | Models |
|---|---|---|
| `lith.call.xai` | `https://api.x.ai/v1/images/generations` | `grok-imagine-image-2.0`, `grok-imagine-image-quality`, `grok-imagine-image` |
| `lith.call.openai` | `https://api.openai.com/v1/images/generations` | `gpt-image-2`, `gpt-image-2-2026-04-21`, `gpt-image-1.5`, `gpt-image-1`, `gpt-image-1-mini` |
| `lith.call.minimax` | `https://api.minimax.io/v1/image_generation` | `image-01` |

```python
build_request(request: ImageRequest, **provider_options) -> dict[str, Any]
unsupported_fields(request: ImageRequest) -> dict[str, str]
generate(request, *, credential=None, **provider_options) -> CallResult
```

`build_request` is pure: it performs no credential lookup and no network access,
which is what [`lith-call --dry-run`](#lithclicall) prints.

**Request bodies.** Each adapter sends only what its provider documents.

| Field sent | xai | openai | minimax |
|---|---|---|---|
| `model`, `prompt`, `n` | ✓ | ✓ | ✓ |
| `aspect_ratio` | ✓ | — | ✓ when in the enum |
| `width` / `height` | — | — | ✓ otherwise |
| `size` | — | ✓ via [`pixel_size`](#pixel_size) | — |
| `response_format` | ✓ `b64_json` | — | ✓ `base64` |
| `resolution` | ✓ when supplied | — | — |
| `quality`, `background` | — | ✓ when supplied | — |
| `output_format`, `output_compression`, `moderation` | — | ✓ | — |
| `seed` | — | — | ✓ when supplied |
| `prompt_optimizer` | — | — | ✓ always `False` |
| `storage_options` | ✓ when supplied | — | — |

`n` is validated against the provider's own ceiling: 1–10 on xAI and OpenAI,
1–9 on MiniMax.

**Provider options** are keyword-only and adapter-specific. `xai` takes
`storage_options` — a mapping of `filename` (required), `expires_after`, and
`public_url` — and switches `response_format` to `url` when it is present.
`openai` takes `output_format`, `output_compression`, and `moderation`.
`minimax` takes none.

**Adapter-specific constants.**

| Name | Module | Value |
|---|---|---|
| `GENERATION_TIMEOUT` | `xai`, `openai` | `180.0` seconds |
| `MODEL` | `minimax` | `"image-01"` |
| `PROMPT_MAX_CHARS` | `minimax` | `1500` |
| `SUPPORTED_ASPECTS` | `minimax` | the eight-ratio enum |

**Raises.** `InvalidRequest` for an out-of-range `n`, an unsupported
`resolution`, an `aspect` of `"auto"`, a malformed `storage_options`, or a ratio
MiniMax cannot represent within 1% using width/height. `minimax` additionally
raises `PromptTooLong` — a subclass of `InvalidRequest` — before any credential
lookup or network call when the prompt exceeds `PROMPT_MAX_CHARS`, reporting the
measured length and the cap.

`prompt_optimizer` is sent explicitly as `False` rather than relying on the
MiniMax default: it rewrites the submitted prompt, which contains the literal
copy block.

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
REQUIRED_BRIEF_KEYS: set[str] = {"topic", "headline", "icon"}
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
| `model` | `"grok-imagine-image-2.0"` |
| `n` | `4` |
| `description` | `None` |
| `brief` | `{}` — then fails validation |

`description` is carried on the dataclass and read by nothing — it is free
text for whoever opens the recipe file.

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
include its leading dot. `cli.run` passes `""` to build a bare stem and then
appends the extension it sniffs from the image bytes.

```python
>>> output_path("/o", "B_brutalist", "32 LANGS", ".png")
PosixPath('/o/B_brutalist_32_langs.png')
```

### `default_output_dir`

```python
default_output_dir(recipe_path: pathlib.Path | str) -> pathlib.Path
```

Returns the directory artifacts for `recipe_path` publish to. A recipe whose
parent directory is named `recipes` resolves to that directory's sibling
`outputs`; any other recipe resolves to `outputs` beside itself.

| Recipe | Result |
|---|---|
| `/repo/recipes/x.json` | `/repo/outputs` |
| `/tmp/x.json` | `/tmp/outputs` |

Resolves symlinks via `Path.resolve()`. Pure — creates nothing.

Both console scripts default to this rather than `Path.cwd() / "outputs"`,
because an agent's working directory is arbitrary and cwd-derived paths
scatter artifacts wherever the session started.

---

## `lith.expand`

### `DEFAULT_PROMPT`

```python
DEFAULT_PROMPT: str
```

The brief-expansion prompt template. Instructs the model to return a JSON
object carrying a full poster spec — `topic`, `headline`, `subtitle`,
`sections` (3–5 objects of `{heading, lines}`), `diagram`, `footer`, `icon`,
and `aspect` — to choose `icon` from
`{gear, lightning, globe, skull, brain, rocket, lock}`, to prefer `2:3` once
there are four or more sections, and to emit no prose outside the JSON block.
It also states the rule the whole design depends on: every word the model
writes is printed verbatim into the image, so it must write only text it wants
rendered, and keep total body copy to 60–140 words.

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
prints either a summary or a call envelope. A non-null `aspect_note` or
[`copy_note`](#copy_note) is printed to stderr as `warning: ...` and carried in
the envelope. [`request_limit_notes`](#request_limit_notes) are printed and
carried as `limit_notes` too. All can fire on the same render.

Precedence with `--recipe`: `n` and `model` come from the recipe, so `--n` and
`--model` are silently ignored. `--seed` and `--out` are read from flags in
both modes. When `--out` is absent, recipe mode anchors the extensionless stem
to [`default_output_dir(recipe)`](#default_output_dir); flag mode uses
`cwd/outputs`. `lith-generate` has no image bytes, so it does not name a format.
The envelope carries that stem; the summary prints it as
`{stem}.<jpg|png|webp>`, matching `cli.run`. An explicit `--out` is used
verbatim in both.

Without `--recipe`, `--topic`, `--style`, and `--headline` are each required;
a missing one triggers `parser.error`, which exits 2.

**Returns** `0`. Argparse errors exit 2 without returning.

---

## `lith.cli.call`

Entry point for `lith-call`. Flags:
[README → `lith-call`](../README.md#lith-call).

### `render_notes`

```python
render_notes(rendered: dict[str, Any]) -> dict[str, Any]
```

Collects `aspect_note`, `copy_note` and `limit_notes` from a
[`render_prompt`](#render_prompt) result, dropping any that are `None`, `""` or
empty. `_run` calls it once, before branching, so `--check` and `--dry-run`
report substitutions too — a caller inspecting the plan is exactly the caller
who needs to know the plan was altered.

Every collected note is printed to stderr as `warning: …` (list-valued
`limit_notes` one line per entry) **and** merged into whichever JSON the command
emits: the routing decision under `--check`, the request preview under
`--dry-run`, the result metadata otherwise.

This exists because it did not. `lith-generate` surfaced all three and
`lith-call` surfaced none, so the command that spends money was the silent one:
a recipe clamped from `16:9` to `3:2` produced a correct image, a zero-byte
stderr, and a JSON payload with no mention of the substitution.

### `routing_decision`

```python
routing_decision(
    recipe_model: str,
    resolved_aspect: str,
    *,
    home=None,
    environ=None,
) -> dict[str, str | None]
```

Returns an inspectable Hermes-versus-`lith-call` decision. Hermes
`image_generate` is selected only when its active model exactly equals the
recipe model and the resolved aspect is `16:9`, `1:1`, or `9:16`; every other
case routes to `lith-call` with the failed condition in `reason`. The Hermes
model comes from `~/.hermes/config.yaml` `image_gen.model`, falling back to
`FAL_IMAGE_MODEL`.

### `request_preview`

```python
request_preview(request: ImageRequest) -> dict[str, Any]
```

Loads the selected adapter and returns its exact method, URL, redacted headers,
request body, and unsupported fields. It performs no credential lookup and no
network call. Provider preconditions still apply; in particular an over-limit
MiniMax prompt fails here rather than printing a payload that cannot succeed.

### `main`

```python
main() -> int
```

`--auth` reports all provider credential resolutions without requiring a
recipe. Other modes load and render the recipe into an [`ImageRequest`](#imagerequest):

| Mode | Effect |
|---|---|
| `--check` | Prints [`routing_decision`](#routing_decision); no credential or network access. |
| `--dry-run` | Prints [`request_preview`](#request_preview); no credential or network access. |
| live | Resolves the selected provider credential, calls [`generate`](#generate), and writes one candidate file per returned index. |

Candidate names are `{family_key}_{slug(headline)}-c{index}{ext}` under `--out`
or the recipe's default output directory. The extension is sniffed from the
bytes; an unrecognized format or duplicate candidate index raises before any
candidate is written. `--emit-json` returns candidate metadata and the complete
`CallResult`; human output prints paths, reported fields, cost, and unsupported
fields.

**Returns** `0`. Argparse errors exit 2. Credential and provider exceptions
propagate.

---

## `lith.imagebytes`

Shared public helpers for recognizing, sizing, and downloading candidate image
bytes. Provider adapters and both image-handling CLIs import these names.

### Module constants

| Constant | Value |
|---|---|
| `ALLOWED_SCHEMES` | `("http", "https")` |
| `DOWNLOAD_TIMEOUT` | `30` (seconds) |
| `DOWNLOAD_MAX_BYTES` | `26214400` (25 MiB) |
| `JPEG_MAGIC` | `b"\xff\xd8\xff"` |
| `PNG_MAGIC` | `b"\x89PNG\r\n\x1a\n"` |

### `image_size`

```python
image_size(body: bytes) -> tuple[int, int] | None
```

Reads `(width, height)` from a PNG IHDR or a JPEG SOF marker.
Returns `None` for WebP — three container variants, and no model in the CLI's
list returns it — and for any header it cannot walk. Header inspection only;
no decode.

### `image_ext`

```python
image_ext(body: bytes) -> str | None
```

Returns `".jpg"` when `body` starts with `JPEG_MAGIC`, `".png"` for
`PNG_MAGIC`, `".webp"` for `b"RIFF"` with `b"WEBP"` at offset 8, and `None`
otherwise. Header inspection only — no decode, no dimension check, no
validation of anything past byte 12.

### `looks_like_image`

```python
looks_like_image(body: bytes) -> bool
```

`image_ext(body) is not None`. The two share one table so a format
the guard admits is always a format the publisher can name.

### `fetch_image`

```python
fetch_image(url: str) -> bytes
```

Applies the same URL, redirect, size, and magic-byte guards as `download`, then
returns the validated bytes without writing a file. Provider adapters use this
for URL-form candidates.

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
5. **Magic bytes.** `looks_like_image` must pass. An HTML error page fails
   here rather than landing on disk as a `.jpg`.

Sends `User-Agent: lith/1.0`. Creates `dst.parent` and writes only after all
five guards pass. Returns `dst`.

The response is accumulated in memory and written in a single `write_bytes`
once every guard has passed, so a failed fetch writes nothing at all.
`DOWNLOAD_MAX_BYTES` therefore bounds resident memory as well as disk.

**Raises** `ValueError` for any guard failure, plus `urllib.error.URLError` /
`HTTPError` / `socket.timeout` from the network layer.

```python
>>> download("file:///etc/hosts", dst)
ValueError: refusing to fetch scheme 'file'; allowed: ('http', 'https')
```

Not covered: DNS rebinding, redirect-count limits, and private-address
filtering — `urllib`'s defaults apply, and a redirect to an internal HTTP host
is permitted.

---

## `lith.cli.run`

Entry point for `lith-run`. Flags: [README → `lith-run`](../README.md#lith-run).

### `aspect_mismatch`

```python
aspect_mismatch(body: bytes, requested: str, tolerance: float = 0.02) -> str | None
```

Returns a description when the delivered frame differs from `requested` by
more than `tolerance` (relative), else `None`. Returns `None` when the
dimensions cannot be read, when `requested` is not `N:M` (`"auto"`), or when
either term is zero — the check never raises and never blocks a publish.

```python
>>> aspect_mismatch(jpeg_720x1280, "2:3")
'requested 2:3 (0.667), received 720x1280 (0.562)'
```

A model may silently substitute a ratio it does not support, and the layout in
the prompt was composed for the frame that was requested, so `cli.run` prints
this as a `[warn]` line rather than letting the substitution pass unnoticed.

### `load_local`

```python
load_local(src: pathlib.Path, dst: pathlib.Path) -> pathlib.Path
```

Copies a local image into the pipeline's staging path. Reads `src` whole, applies
the same `looks_like_image` check, creates `dst.parent`, and writes — unless
`src` and `dst` resolve to the same file, in which case the write is skipped.
Returns `dst`.

**Raises** `FileNotFoundError` if `src` is not a file; `ValueError` if the
magic-byte check fails.

### `main`

```python
main() -> int
```

Loads the recipe, resolves the output directory from `--output-dir` or
[`default_output_dir`](#default_output_dir), renders the prompt, and derives
the output stem via `output_path(..., "")`. Branches two ways:

| Branch | Effect |
|---|---|
| No image source | Prints recipe, family, style, aspect, model, `n`, prompt, and `{stem}.<jpg\|png\|webp>`. Writes nothing. |
| Image source | Stages the bytes at `{stem}.part`, warns if [`aspect_mismatch`](#aspect_mismatch) finds drift, then `Path.replace`s that onto `{stem}` plus the extension `image_ext` reads from the first 12 bytes. |

`--strict` promotes that drift warning to exit code 1. The publish still
happens first: the delivered bytes are what you need in order to see how the
frame was substituted, so withholding them would make the failure harder to
diagnose, not safer. The exit code — not the file's existence — is the signal a
caller should branch on.

Output stem: `{output_dir}/{family_key}_{slug(headline)}`. The extension is not
known until the bytes arrive — Grok returns JPEG, `gpt-image-1` returns PNG —
so the artifact is named after what actually landed. Nothing is re-encoded, and
the published file is overwritten without prompting on a re-run.

The staging file exists because the extension cannot be chosen until the bytes
are in hand: they land at `{stem}.part`, are inspected, then renamed. It is not
a crash-safety measure — `download` and `load_local` both write their whole
body in one call after their guards pass, so a failed fetch leaves no file at
all. A `.part` survives only if the rename itself fails.

`--image-url` and `--image-file` are a mutually exclusive argparse group.
Progress lines print with `flush=True`.

**Returns** `0`, or `1` when `--strict` is set and the frame drifted. Argparse
errors exit 2. Guard failures from `download` or `load_local` propagate as
tracebacks.

---

## Exception summary

| Exception | Raised by | Trigger |
|---|---|---|
| `KeyError` | `render_prompt` | Template slot outside the supported seven |
| `KeyError` | `load_recipe` | Missing `style` key |
| `KeyError` | `get_family`, `Recipe.family_key` | Style letter outside `A`–`G` |
| `TypeError` | `render_prompt` | `Recipe` with a brief, or mapping without one |
| `ValueError` | `format_spec`, `render_prompt` | A brief section with no `heading` |
| `ValueError` | `load_recipe` | Missing required brief keys |
| `ValueError` | `parse_brief_response`, `expand_brief` | No decodable JSON object |
| `ValueError` | `pixel_size` | Unknown/non-pixel model, invalid ratio, or unreachable size |
| `ValueError` | `provider_for_model`, `generate` | Unknown model or wrong-provider credential |
| `ValueError` | `download` | Bad scheme, bad redirect, oversize body, non-image bytes |
| `ValueError` | `load_local` | Non-image bytes |
| `MissingCredential` | `resolve_credential`, provider `generate` | All four credential tiers exhausted |
| `CredentialFileError` | `resolve_credential` | Existing `.env` or `auth.json` unreadable/malformed |
| `InvalidRequest` | provider adapters | Invalid request field or combination before/during a call |
| `PromptTooLong` | MiniMax adapter | Prompt exceeds 1500 characters before network access |
| `AuthError` | provider transport | Invalid/unauthorized credential |
| `RateLimited` | provider transport | HTTP/provider rate limit |
| `ContentRejected` | provider transport | Content or safety rejection |
| `ProviderError` | provider transport/adapters | Other transport, response-shape, or provider error |
| `FileNotFoundError` | `load_recipe`, `load_styles`, `load_local` | Missing input file |
| `json.JSONDecodeError` | `load_recipe`, `load_styles` | Malformed JSON |
| `subprocess.CalledProcessError` | `expand_brief` | `llm_cmd` exits nonzero |
| `subprocess.TimeoutExpired` | `expand_brief` | Command exceeds `timeout` |

The call-specific exceptions above are custom types. `AuthError`,
`RateLimited`, `ContentRejected`, and `InvalidRequest` subclass `ProviderError`;
`PromptTooLong` subclasses `InvalidRequest`. All carry a human-readable message,
and provider errors may carry `status_code` and `payload`.

---

## Side effects and determinism

| Function | Filesystem | Network | Subprocess | Deterministic |
|---|---|---|---|---|
| `render_prompt` | — | — | — | yes |
| `format_spec`, `format_layout` | — | — | — | yes |
| aspect helpers, `pixel_size` | — | — | — | yes |
| `slug`, `output_path` | — | — | — | yes |
| `load_recipe` | read | — | — | yes |
| `load_styles`, `get_family` | read | — | — | yes |
| `parse_brief_response` | — | — | — | yes |
| `expand_brief` | — | via `llm_cmd` | `llm_cmd` | no |
| `resolve_credential` | read | — | — | yes for a fixed environment/filesystem |
| provider `build_request` | — | — | — | yes |
| `lith.call.generate` | read credentials | yes | — | no |
| `request_preview` | — | — | — | yes |
| `routing_decision` | config read | — | — | yes for fixed inputs/config |
| `download` | write | yes | — | no |
| `load_local` | read + write | — | — | yes |

`render_prompt` is a pure function of its arguments plus the bundled
`styles.json`, so the same recipe yields the same prompt across runs and
machines. Randomness enters through `expand_brief`'s model and provider image
generation. Request building, aspect translation, and routing decisions remain
deterministic.

Output paths are derived, not unique: re-running a recipe overwrites the
previous artifacts.

---

## See also

- [README → CLI reference](../README.md#cli-reference) — the three console scripts
- [README → Recipe format](../README.md#recipe-format) — the JSON schema
- [About the pipeline](explanation-pipeline.md) — provider handoffs and deliberate omissions
- [Tutorial: your first announcement image](tutorial-first-image.md) — the API in use
