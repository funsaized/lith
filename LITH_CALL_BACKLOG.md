# `lith-call` — backlog

A thin provider layer that turns a lith envelope into a real image, across xAI,
OpenAI and MiniMax, with a uniform surface for both human and agent callers.

Grounded in:

- [xAI images REST reference](https://docs.x.ai/developers/rest-api-reference/inference/images)
- [OpenAI image generation guide](https://developers.openai.com/api/docs/guides/image-generation)
- [MiniMax text-to-image](https://platform.minimax.io/docs/api-reference/image-generation-t2i) ·
  [image-to-image](https://platform.minimax.io/docs/api-reference/image-generation-i2i)
- [Hermes image generation](https://hermes-agent.nousresearch.com/docs/user-guide/features/image-generation)

---

## Why this exists

Two live sweeps of the 34-recipe testbed were invalidated before the model ever
saw a correct input. Both failed the same way: lith emits five fields and has no
way to assert any of them arrived. The bridge in use accepts `prompt` and
discards the rest.

Reading the provider docs settles three questions the sweeps could not.

**The three-bucket aspect constraint is not a provider limit.** xAI accepts
fourteen `aspect_ratio` values including `2:3`, `3:2`, `20:9` and `auto`.
MiniMax accepts eight plus explicit `width`/`height`. The
`landscape|square|portrait` enum belongs to Hermes' `image_generate`, and every
frame drift across both sweeps traces to that translation.

**`resolution` exists on xAI — `1k` or `2k`.** Panel area is the one variable
that actually correlated with copy fidelity across both runs: rows 03 and 07
went from garbled to clean the moment their frame changed from 1280×720 to
1024×1024. A `2k` render is the direct lever on the real failure mode, and it
has never been pulled.

**No provider accepts a negative prompt.** Not xAI, not OpenAI, not MiniMax.
lith has emitted `negative_prompt` on every render since the spec model landed
and it has never reached a model. The run-2 conclusion that "the cliff was the
missing negative_prompt" was not merely unproven — it was describing a field
that no provider in this matrix can receive.

---

## Grounded capability matrix

### xAI — `POST https://api.x.ai/v1/images/generations`

`Authorization: Bearer $XAI_API_KEY`

| Parameter | Values |
|---|---|
| `model` | `grok-imagine-image-2.0` (per docs examples) |
| `prompt` | string, required |
| `n` | integer |
| `aspect_ratio` | `1:1` `3:4` `4:3` `9:16` `16:9` `2:3` `3:2` `9:19.5` `19.5:9` `9:20` `20:9` `1:2` `2:1` `auto` |
| `resolution` | `1k` `2k` |
| `response_format` | `url` `b64_json` |
| `storage_options` | `{filename (required), expires_after (≤2592000s), public_url}` |
| `user` | abuse-detection identifier |

Response: `data[]` with `url`, `b64_json`, `mime_type`, `file_output`,
`storage_error`; plus `usage` carrying `cost_in_usd_ticks`.

No negative prompt. Rate limits and error codes are not documented.

### OpenAI — `POST /v1/images/generations` and `/v1/images/edits`

`Authorization: Bearer $OPENAI_API_KEY`

| Parameter | Values |
|---|---|
| `model` | `gpt-image-2` `gpt-image-1.5` `gpt-image-1` `gpt-image-1-mini` |
| `size` | `1024x1024` `1024x1536` `1536x1024` `2048x2048` `2048x1152` `3840x2160` `2160x3840` `auto` |
| `quality` | `low` `medium` `high` `auto` |
| `n` | integer ≥ 1 |
| `response_format` | `b64_json` (default) `url` |
| `moderation` | `auto` `low` |
| `stream` / `partial_images` | boolean / `0`–`3` |
| edits only | `image` (file or array), `mask`, `output_compression` `0`–`100` |

Size constraints: max edge ≤ 3840, both edges multiples of 16, aspect ≤ 3:1,
total pixels 655,360–8,294,400.

**OpenAI takes pixel sizes, not ratios.** The size enum reduces to five usable
aspects: `1:1`, `2:3`, `3:2`, `16:9`, `9:16`.

### MiniMax — `POST https://api.minimax.io/v1/image_generation`

`Authorization: Bearer $MINIMAX_API_KEY`

| Parameter | Values |
|---|---|
| `model` | `image-01` (t2i + i2i), `image-01-live` (i2i) |
| `prompt` | string, required, ≤ 1500 chars |
| `aspect_ratio` | `1:1` `16:9` `4:3` `3:2` `2:3` `3:4` `9:16` `21:9` — default `1:1` |
| `width` / `height` | 512–2048, divisible by 8; **overridden by `aspect_ratio`** |
| `n` | 1–9, default 1 |
| `seed` | integer |
| `prompt_optimizer` | boolean, default false |
| `response_format` | `url` (default, expires 24h) `base64` |
| `subject_reference` | `[{type: "character", image_file: URL or data: URL}]`, one only, <10MB, JPG/PNG |

Response: `{id, data:{image_urls[]|image_base64[]}, metadata:{success_count,
failed_count}, base_resp:{status_code, status_msg}}`.

Status codes: `0` ok, `1002` rate limit, `1004` auth, `1008` balance, `1026`
sensitive content, `2013` invalid params, `2049` invalid key.

**MiniMax is the only provider that truly batches** — `n` up to 9 in one call.

### Hermes `image_generate` — what it can and cannot do

| Parameter | Values |
|---|---|
| `prompt` | text |
| `aspect_ratio` | `landscape` `square` `portrait` |
| `image_url` | source image for editing |
| `reference_image_urls` | 9–16 depending on backend |
| `upscale` | boolean |
| `seed`, `num_inference_steps` | filtered per-model |

Routes to FAL (default `fal-ai/flux-2/klein/9b`), OpenAI (`gpt-image-1.5`,
`gpt-image-2`), xAI, Krea, and the Nous gateway. Active model lives in
`config.yaml` under `image_gen.model`, with `FAL_IMAGE_MODEL` as fallback.
Counts come from `max_parallel_requests` (default 4). No model parameter, no
negative prompt, no fine-grained ratio.

---

## Defects in current lith that the docs expose

These are wrong today, independent of whether `lith-call` ships.

| Location | Problem |
|---|---|
| `aspect.MODEL_ASPECTS["gpt-image-2"]` | Claims 15 ratios including `5:4`, `4:5`, `3:1`, `1:3`, `21:9`, `9:21`. The documented size enum supports **five**. Every clamp decision for this model is currently wrong. |
| `aspect.MODEL_ASPECTS["grok-imagine-image-2.0"]` | Missing `9:19.5`, `19.5:9`, and `auto`. |
| `aspect.MODEL_ASPECTS` | No `gpt-image-1.5` or `gpt-image-1-mini`. |
| `minimax-image` | Not a real model id anywhere in MiniMax's docs. The ids are `image-01` and `image-01-live`. Deliberately left unlisted so it is never clamped — it should be listed, with its 8-value enum. |
| `MODEL_ASPECTS` shape | Models whose real constraint is a **pixel size** (OpenAI) or a **ratio-or-WxH pair** (MiniMax) cannot be expressed as a ratio set. The table needs a richer value type. |
| `negative_prompt` | Emitted on every render, deliverable to no provider in this matrix. Needs an explicit policy rather than silent futility. |
| `cli/generate.py --model` | `choices` list carries the stale ids. |

**Do these first.** They are cheap, they are pure-table edits with existing test
coverage, and every one of them currently produces a confidently wrong clamp.

---

## Package design

```
src/lith/call/
├── __init__.py      ImageRequest, Candidate, CallResult, generate()
├── creds.py         ~/.hermes/.env loader, shell override
├── http.py          POST-JSON over urllib, shared guards
├── capability.py    doc-grounded per-model capability records
├── xai.py
├── openai.py
└── minimax.py
src/lith/cli/call.py  → console script `lith-call`
```

Constraints carried over from the rest of the package: **stdlib only**, no new
runtime dependency, no vendor SDK. `urllib.request` already backs `download()`
in `cli/run.py`; the same size cap, scheme check and magic-byte check apply to
every byte this layer returns.

The library stays network-free. `lith.call` lives beside `lith.cli` on the
network side of the line, and `render`/`aspect`/`layout` never import it.

### Uniform request

```python
@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    model: str
    aspect: str                      # "W:H" — lith's resolved value, verbatim
    n: int = 1
    seed: int | None = None
    resolution: str | None = None    # xAI 1k/2k
    quality: str | None = None       # OpenAI low/medium/high
    reference_image: str | None = None
    negative_prompt: str | None = None
```

Fields a provider cannot express are **reported, never smuggled**. Nothing is
appended to `prompt` under any circumstance — a negative prompt pasted into a
positive prompt asks the model for what it was meant to forbid, and adds text
the model can letter into the frame.

### Uniform result

```python
@dataclass
class Candidate:
    index: int
    data: bytes                  # always bytes — b64 decoded or URL fetched here
    mime: str
    dimensions: tuple[int, int] | None

@dataclass
class CallResult:
    candidates: list[Candidate]
    model_reported: str | None
    aspect_reported: str | None
    unsupported: dict[str, str]  # field -> why it could not be sent
    cost: str | None
    raw: dict                    # provider response verbatim
```

`unsupported` and `raw` are the point. Every failure in this project's history
was a field silently discarded, and both sweeps needed manual forensics to
discover it. This makes it a return value.

### Aspect handling per provider

| Provider | Strategy |
|---|---|
| xAI | Pass `aspect` through when in the enum; otherwise `nearest_supported`, recorded in `unsupported`. |
| OpenAI | Map ratio → nearest allowed **size string**, honouring the edge/pixel constraints. Never send a ratio. |
| MiniMax | Pass through when in the enum; otherwise compute `width`/`height` within 512–2048 ÷ 8 — the only provider that can hit an arbitrary ratio exactly. |

`resolve_aspect` keeps owning the decision; this layer only translates it into
each provider's vocabulary and reports the translation.

### Credentials

`creds.py` loads `~/.hermes/.env` first, then lets the shell environment
override — so a one-off `XAI_API_KEY=… lith-call …` wins without editing a file.

Keys: `XAI_API_KEY`, `OPENAI_API_KEY`, `MINIMAX_API_KEY`. A missing key raises
naming the variable and the file it was looked for in. Keys are never logged,
never echoed into `raw`, and never written to disk.

### CLI

```
lith-call --recipe PATH [--out DIR] [--n N] [--resolution 1k|2k]
          [--quality low|medium|high] [--seed N] [--dry-run] [--emit-json]
lith-call --check --recipe PATH        # routing decision only, no call
```

`--dry-run` prints the exact request body per provider, keys redacted. Given
this project's history, being able to see the payload without spending money is
worth more than any other flag here.

Candidates land as `{stem}-c{i}.{ext}`, extension from magic bytes, never from
the model id. Publishing stays with `lith-run`, which owns the frame check.

---

## Hermes integration

The skill introspects before choosing a path:

1. Read the recipe's `model`.
2. Read Hermes' active model — `config.yaml` → `image_gen.model`, falling back
   to `FAL_IMAGE_MODEL`.
3. Read the envelope's resolved `aspect_ratio`.

Use `image_generate` only when **both** hold:

- the configured Hermes model equals the recipe's `model`, and
- the resolved aspect is one of `16:9`, `1:1`, `9:16`

Otherwise call `lith-call`. The second condition matters as much as the first:
`image_generate` accepts only three buckets, so a matching model still delivers
the wrong frame for `2:3`, `3:2`, `20:9` and every other ratio lith resolves.

`lith-call --check` prints this decision and its reason, so the routing is
inspectable rather than a judgment the agent makes silently each run.

---

## Backlog

### Phase 0 — correct the capability table *(no new code paths)*

- [ ] Rewrite `MODEL_ASPECTS` from the matrix above; add `gpt-image-1.5`,
      `gpt-image-1-mini`, `image-01`, `image-01-live`; drop `minimax-image`.
- [ ] Widen the capability value type so OpenAI's pixel sizes and MiniMax's
      ratio-or-WxH both express, rather than forcing everything into ratio sets.
- [ ] Update `cli/generate.py --model` choices; update the testbed rows pinned
      to `minimax-image` and `gpt-image-2`.
- [ ] Decide the `negative_prompt` policy and document it.

**Acceptance:** every ratio in `MODEL_ASPECTS` traces to a cited doc value; the
existing 210 tests pass; testbed rows resolve to producible frames.

### Phase 1 — the layer, xAI only

- [ ] `creds.py`, `http.py`, `capability.py`, `xai.py`, `ImageRequest`/`CallResult`.
- [ ] `lith-call` with `--dry-run`, `--emit-json`, `--check`.
- [ ] Fixture-based tests: request-body shape per provider, `unsupported`
      population, b64 decode, magic-byte rejection, missing-key error text.

**Acceptance:** one real call at `aspect_ratio: "2:3"` returns a ~0.667 frame,
`lith-run --strict` exits 0, and `CallResult.model_reported` shows the id that
actually served. That single result closes the question two sweeps could not.

### Phase 2 — OpenAI and MiniMax

- [ ] `openai.py` — ratio→size mapping, `quality`, `n`, edits endpoint.
- [ ] `minimax.py` — `n` batching 1–9, `prompt_optimizer`, `seed`, width/height
      fallback, `base_resp.status_code` mapped to real exceptions.

**Acceptance:** the same recipe renders on all three providers; every testbed
model id is callable; MiniMax returns n>1 candidates in a single request.

### Phase 3 — exploit what is unique

- [ ] xAI `resolution: 2k` — **run the density rows at 2k and settle whether
      panel area is the copy-fidelity variable.** This is the highest-value
      experiment available and it needs one flag.
- [ ] xAI `storage_options` for stable public URLs instead of expiring ones.
- [ ] OpenAI `quality` sweep; `partial_images` for progressive preview.
- [ ] MiniMax `subject_reference` for character consistency across a series.

### Phase 4 — skill and docs

- [ ] SKILL.md: the routing rule, `lith-call` usage, `--check` before a sweep.
- [ ] README CLI reference; a `lith.call` section in the Python API reference.
- [ ] Rerun the 34-recipe testbed through `lith-call` with all six ids live.

---

## Open questions

**Per-model size enums on OpenAI.** The guide presents one size table across
`gpt-image-2`, `gpt-image-1.5`, `gpt-image-1` and `gpt-image-1-mini`. lith
currently records `gpt-image-1` as supporting only `1024x1024`, `1536x1024`,
`1024x1536`, which is narrower. Verify per model before Phase 2 — a wrong
narrowing produces a needless clamp, a wrong widening produces a silent reframe.

**xAI `n` semantics.** Documented as an integer with no stated range. Whether
one request returns n images, and whether cost scales linearly, needs one
empirical check.

**`background` on OpenAI.** Referenced in community usage but not present in the
returned parameter table. Do not implement until confirmed against the docs.

**xAI image edits.** Only `/v1/images/generations` appears in the reference. If
an edits endpoint exists it is undocumented there; treat i2i on xAI as
unavailable rather than guessing a shape.

**Hermes gateway billing.** `use_gateway` and the Nous subscription path may
bill differently from a direct provider key. Worth knowing before a sweep that
bypasses Hermes on purpose.
