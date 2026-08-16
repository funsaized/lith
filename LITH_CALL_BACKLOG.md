# `lith-call` — backlog

A provider layer that turns a lith envelope into real image bytes across xAI,
OpenAI and MiniMax, with one surface for human and agent callers.

## How to use this document

Sections 1–3 are **ground truth**: API facts already crawled and verified
against provider docs, and measurements already taken against this repo. Do not
re-research them. If you find one is wrong, correct it here in the same change
that acts on it.

Section 5 is the **task graph**. Each task carries:

| Field | Meaning |
|---|---|
| **ID** | Stable handle, e.g. `P0-2`. Reference it in commits and PRs. |
| **Needs** | Task IDs that must land first. No other ordering is implied. |
| **Env** | `OFFLINE` — no network, no credentials, fully testable in CI. `KEY:<provider>` — requires a live API key and spends money. |
| **Files** | Every path the task is expected to touch. |
| **Done** | The observable condition. If you cannot check it, the task is not done. |

Tasks with the same **Needs** and no shared **Files** can run in parallel.
`OFFLINE` tasks are safe for any agent; `KEY:` tasks require a human to have
provisioned credentials and should never be attempted speculatively.

House rules that override any instinct to the contrary:

- **Standard library only.** No `requests`, no `httpx`, no vendor SDK. The
  package has zero runtime dependencies and that is a feature.
- **Never append to `prompt`.** A field the provider cannot accept is reported
  in `CallResult.unsupported`, never smuggled into the prompt text. A negative
  prompt pasted into a positive prompt asks the model for what it was meant to
  forbid, and adds text the model can letter into the frame.
- **Never infer a parameter from silence.** xAI's edits endpoint omits two
  fields from its own table that provably work. Absence from a doc is not
  evidence of absence from the API.
- Billing is the caller's. Pass `cost` through; never estimate, budget or cap.

---

## 1. Why this exists

Two live sweeps of the 34-recipe testbed were invalidated before the model saw a
correct input. Both failed identically: lith emits five fields and cannot assert
any of them arrived. The bridge in use accepts `prompt` and discards the rest.

Reading the provider docs settles what 68 generations could not.

**The three-bucket aspect constraint is not a provider limit.** xAI accepts
fourteen `aspect_ratio` values. MiniMax accepts eight plus explicit
`width`/`height`. gpt-image-2 accepts arbitrary pixel sizes. The
`landscape|square|portrait` enum belongs to Hermes' `image_generate` alone, and
every frame drift across both sweeps traces to that translation.

**`resolution: 2k` exists on xAI.** Panel area is the one variable that
correlated with copy fidelity across both runs — rows 03 and 07 went from
garbled to clean when their frame changed from 1280×720 to 1024×1024. This is
the direct lever on the real failure mode and it has never been pulled.

**No provider in this matrix accepts a negative prompt.** lith has emitted
`negative_prompt` on every render since the spec model landed and it has never
reached a model.

---

## 2. Ground truth — provider APIs

### 2.1 xAI

Source: [REST reference](https://docs.x.ai/developers/rest-api-reference/inference/images) ·
[editing](https://docs.x.ai/developers/model-capabilities/images/editing)

**`POST https://api.x.ai/v1/images/generations`** · `Authorization: Bearer $XAI_API_KEY`

| Parameter | Type | Values |
|---|---|---|
| `model` | `string \| null` | optional; `grok-imagine-image-2.0` |
| `prompt` | `string` | required |
| `n` | `integer \| null` | default `1`, **min 1, max 10** |
| `aspect_ratio` | `null \| string` | `1:1` `3:4` `4:3` `9:16` `16:9` `2:3` `3:2` `9:19.5` `19.5:9` `9:20` `20:9` `1:2` `2:1` `auto` |
| `resolution` | `null \| string` | `1k` `2k` |
| `response_format` | `string \| null` | **default `url`**; or `b64_json` |
| `storage_options` | `null \| object` | `{filename (required), expires_after ≤2592000s, public_url}` |
| `user` | `string \| null` | abuse-detection identifier |

Response: `data[]` of `{url, b64_json, mime_type, revised_prompt, file_output,
storage_error}` plus `usage.cost_in_usd_ticks`.

A measured `P1-6` call on 2026-08-16 omitted top-level `model` and
`aspect_ratio`, consistent with that documented response shape. For a
successful request carrying an explicit model id, `CallResult.model_reported`
therefore uses the response value when present and otherwise the exact model id
the endpoint accepted. `aspect_reported` does not make the same fallback: the
returned pixel dimensions are the evidence for whether the requested frame was
honoured.

`revised_prompt` is `""` in the reference example. If it is ever populated the
model rewrote our prompt — surface it, because authored-not-improvised copy is
this pipeline's entire premise.

**`POST https://api.x.ai/v1/images/edits`** — `application/json` only;
**`multipart/form-data` is not supported**.

The documented Request Body lists **only `prompt`**. The adjacent working
example also sends `model` and `image: {url, type: "image_url"}`. `image.url`
accepts a public URL, a base64 data URI, or a Files API `file_id`.

Because two provably-working fields are missing from that table, nothing can be
inferred about `mask`, `n`, `aspect_ratio` or `resolution` here. See `Q-1`.

### 2.2 OpenAI

Source: [image generation guide](https://developers.openai.com/api/docs/guides/image-generation) ·
[API reference](https://developers.openai.com/api/docs/api-reference/images)

**`POST /v1/images/generations`** and **`/v1/images/edits`** ·
`Authorization: Bearer $OPENAI_API_KEY`

| Parameter | Values |
|---|---|
| `model` | `gpt-image-2` (snapshot `gpt-image-2-2026-04-21`) `gpt-image-1.5` `gpt-image-1` `gpt-image-1-mini` |
| `size` | **varies by model — see below** |
| `quality` | `high` `medium` `low` `auto` (default) |
| `background` | `transparent` `opaque` `auto` (default) — *"only supported for GPT image models that support transparent backgrounds"* |
| `output_format` | `png` `jpeg` `webp` |
| `output_compression` | `0`–`100`, default `100`; only with `webp`/`jpeg` |
| `n` | **1–10** |
| `moderation` | `low` `auto` (default) |
| `stream` / `partial_images` | boolean default `false` / `0`–`3` |
| edits only | `image` (file or array), `mask` |

**Correction measured in `P2-3` on 2026-08-16:** GPT Image rejects
`response_format` with HTTP 400 `unknown_parameter`. The current official
[image generation guide](https://developers.openai.com/api/docs/guides/image-generation)
shows GPT Image requests without that field and states that the Image API
returns base64-encoded image data. `response_format` is therefore not sent for
the GPT Image models in this table; `data[].b64_json` is read directly.

**`size` splits by model. This is the single most important line in the table:**

| Model | `size` |
|---|---|
| `gpt-image-2` | **Arbitrary `WIDTHxHEIGHT`** + `auto` |
| `gpt-image-1.5` | `1024x1024` `1536x1024` `1024x1536` `auto` |
| `gpt-image-1` | `1024x1024` `1536x1024` `1024x1536` `auto` |
| `gpt-image-1-mini` | `1024x1024` `1536x1024` `1024x1536` `auto` |

gpt-image-2 constraints, verbatim:

- *"Maximum edge length must be less than or equal to `3840px`"*
- *"Both edges must be multiples of `16px`"*
- *"Long edge to short edge ratio must not exceed `3:1`"*
- *"Total pixels must be at least `655,360` and no more than `8,294,400`"*

Above `2560x1440` is documented as experimental. Note the constraints interact:
an extreme ratio cannot also reach maximum pixels, because the long edge hits
3840 first.

**OpenAI takes pixel sizes, never ratios.** The three 1.x models reduce to
exactly `1:1`, `3:2`, `2:3`. gpt-image-2 is a *continuous range*, not a set.

### 2.3 MiniMax

Source: [text-to-image](https://platform.minimax.io/docs/api-reference/image-generation-t2i) ·
[image-to-image](https://platform.minimax.io/docs/api-reference/image-generation-i2i)

**`POST https://api.minimax.io/v1/image_generation`** · `Authorization: Bearer $MINIMAX_API_KEY`

| Parameter | Values |
|---|---|
| `model` | `image-01` (t2i + i2i), `image-01-live` (i2i only) |
| `prompt` | required, **max 1500 characters** — see §3.1 |
| `aspect_ratio` | `1:1` (default) `16:9` `4:3` `3:2` `2:3` `3:4` `9:16` `21:9` |
| `width` / `height` | 512–2048, ÷8; **overridden by `aspect_ratio`** |
| `n` | 1–9, default 1 |
| `seed` | integer |
| `prompt_optimizer` | boolean, default `false` |
| `response_format` | `url` (default, expires 24h) `base64` |
| `subject_reference` | `[{type: "character", image_file}]` — one only, <10MB, JPG/PNG |

Response: `{id, data:{image_urls[]|image_base64[]}, metadata:{success_count,
failed_count}, base_resp:{status_code, status_msg}}`.

Status codes: `0` ok · `1002` rate limit · `1004` auth · `1008` balance ·
`1026` sensitive content · `2013` invalid params · `2049` invalid key.

**MiniMax reports errors in a `200` body.** `base_resp.status_code` must be
checked on every response; HTTP status alone is not sufficient.

### 2.4 Hermes `image_generate`

Source: [Hermes docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/image-generation)

| Parameter | Values |
|---|---|
| `prompt` | text |
| `aspect_ratio` | `landscape` `square` `portrait` |
| `image_url` | source image for editing |
| `reference_image_urls` | 9–16 depending on backend |
| `upscale` | boolean |
| `seed`, `num_inference_steps` | filtered per-model |

Routes to FAL (default `fal-ai/flux-2/klein/9b`), OpenAI (`gpt-image-1.5`,
`gpt-image-2`), xAI, Krea, Nous gateway. Active model in `config.yaml` under
`image_gen.model`, fallback `FAL_IMAGE_MODEL`. Counts via
`max_parallel_requests` (default 4). **No model parameter, no negative prompt,
no fine-grained ratio.**

### 2.5 This machine's actual configuration

Measured, not assumed. Re-check before relying on it.

`~/.hermes/config.yaml`:

```yaml
image_gen:
  provider: xai
  use_gateway: false
  model: grok-imagine-image-quality
  xai:
    storage:
      enabled: true
      public_url: true
```

Two consequences.

**`lith-call` is the primary path, not a fallback.** Hermes' active model is
`grok-imagine-image-quality`; every recipe defaults to `grok-imagine-image-2.0`.
Under the routing rule in §4 the models never match, so every recipe routes to
`lith-call` today. Resolve deliberately — align the recipes, align the Hermes
config, or accept `lith-call` as primary — rather than discovering it at run
time.

**xAI `storage_options` is already proven in this environment.**
`storage.enabled: true, public_url: true` is why probe images returned as
`files-cdn.x.ai/…/hermes-xai-image-….png`. `P3-3` is lower-risk than it looks.

**Credentials available here, by tier (§4):**

| Provider | Resolves from | Live-callable today |
|---|---|---|
| xAI | Tier 4 — `auth.json` → `xai-oauth`, `base_url: https://api.x.ai/v1` | **yes** |
| MiniMax | Tier 3 — `~/.hermes/.env` → `MINIMAX_API_KEY` | yes, but see §3.1 |
| OpenAI | Tier 3 — `~/.hermes/.env` → `OPENAI_API_KEY` | credential present; live validity pending `P2-3` |

The xAI credential is a SuperGrok device-code OAuth token, not an API key, and
it is pointed at the developer API base URL — which is why Hermes generates
images with `use_gateway: false` and no `XAI_API_KEY` anywhere. `P1-6` is
therefore unblocked.

OpenAI changed after the original snapshot. A measured `lith-call --auth`
re-check on 2026-08-16 resolves a nonempty `OPENAI_API_KEY` from tier 3; `P2-3`
will establish its live validity. The `openai-codex` entry still has
`base_url: https://chatgpt.com/backend-api/codex` — the Codex backend, not
`api.openai.com` — and tier 4's base-URL check still rejects it by design. The
tier-3 API key, not that OAuth entry, is what removes the credential blocker.

The MiniMax conventional API key remains available, but cannot render a lith
poster without the out-of-scope compact templates (§3.1).

---

## 3. Findings that shape the plan

### 3.1 BLOCKER — MiniMax cannot render a lith poster

MiniMax caps `prompt` at 1500 characters. Measured against this repo:

| Family | Template alone (empty brief) | vs 1500 cap |
|---|---|---|
| `G_log` | 1349 | 151 chars headroom |
| `B_brutalist` | 1470 | 30 chars headroom |
| `E_screenshot` | 1477 | 23 chars headroom |
| `C_patent` | 1507 | **over** |
| `A_sticker` | 1539 | **over** |
| `D_manga` | 1634 | **over** |
| `F_woodcut` | 1717 | **over** |

Across all 34 testbed recipes the rendered prompt runs **1555–3478 characters.
Zero fit.** Four of seven families exceed the cap before a single line of copy
is added; the other three have less headroom than one section consumes.

This is not an adapter detail — it means **MiniMax cannot serve this pipeline's
actual workload**. Treat the adapter as built-for-completeness with a hard
precondition, not as a working provider for posters. Resolving it properly
requires a compact template variant per family, which is a design-language
change and is deliberately out of scope. See §6.

### 3.2 The capability model is the real blocker for everything else

`aspect.MODEL_ASPECTS` is `dict[str, set[str]]`. The three providers need three
different shapes:

| Provider | Real constraint |
|---|---|
| xAI, MiniMax | ratio enum — a set works |
| OpenAI 1.x | fixed pixel-size list |
| gpt-image-2 | a *range*: ÷16, ratio `[1:3, 3:1]`, 655,360–8,294,400 px, edge ≤ 3840 |

A set cannot express the last two. Fixing the entries without fixing the type
relocates the wrongness rather than removing it. This is `P0-1` and almost
everything depends on it.

### 3.3 Current table defects

| Entry | Status |
|---|---|
| `gpt-image-1` = `{1:1, 3:2, 2:3}` | **Correct.** Verified against the per-model size table. Copy to `gpt-image-1.5` and `gpt-image-1-mini`. |
| `gpt-image-2` = 15 ratios | All 15 are legal, but the model accepts *any* ratio in `[1:3, 3:1]`. The set **under-permits**: `20:9` (2.222, well inside) is clamped to `21:9` or `2:1` for no reason. |
| `grok-imagine-image-2.0` | Missing `9:19.5`, `19.5:9`, `auto`. |
| `minimax-image` | Not a real id. The t2i id is `image-01`. Currently unlisted, so never clamped. |
| absent | `gpt-image-1.5`, `gpt-image-1-mini`, `gpt-image-2-2026-04-21`, `image-01` |
| `n` | No model records a maximum. xAI 10, OpenAI 10, MiniMax 9 — and `recipe.n` defaults to **4**, so this is reachable today. |
| prompt length | No model records a cap. MiniMax's 1500 is violated by every recipe. |

### 3.4 Layering

`download`, `_looks_like_image`, `_image_ext`, `_image_size` and
`aspect_mismatch` all live in `src/lith/cli/run.py`. `lith.call` needs the first
four. A provider module importing from `lith.cli` is backwards.

Extract them to `src/lith/imagebytes.py` first (`P0-5`) so both consumers import
downward.

The purity rule to preserve: `render`, `aspect`, `layout`, `recipe`, `styles`,
`paths` touch no network and import neither `cli` nor `call`. `P0-6` makes that
a test rather than a convention.

---

## 4. Target architecture

```
src/lith/
├── imagebytes.py       NEW  download, magic-byte sniff, dimensions  (P0-5)
├── aspect.py           MOD  capability records, pixel_size          (P0-1..4)
├── call/               NEW
│   ├── __init__.py          ImageRequest, Candidate, CallResult, generate()
│   ├── creds.py             ~/.hermes/.env then shell override
│   ├── http.py              POST-JSON over urllib, retries, errors
│   ├── capability.py        model → provider + limits
│   ├── xai.py
│   ├── openai.py
│   └── minimax.py
└── cli/
    └── call.py         NEW  lith-call console script
```

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
    background: str | None = None    # OpenAI transparent/opaque
    negative_prompt: str | None = None
```

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
    revised_prompt: str | None
    unsupported: dict[str, str]  # field -> why it could not be sent
    cost: str | None
    raw: dict                    # provider response, verbatim, keys redacted
```

`unsupported` and `raw` are the point of the whole design. Every failure in this
project's history was a silently discarded field that took manual forensics to
find. This makes it a return value.

### Aspect translation

| Provider | Strategy |
|---|---|
| xAI | Pass through when in the 14-value enum; else `nearest_supported`, recorded. |
| OpenAI 1.x | Nearest of three fixed sizes; only `1:1`/`3:2`/`2:3` land exactly. |
| gpt-image-2 | Solve for `WIDTHxHEIGHT` — ÷16, ratio in range, pixel budget, edge ≤ 3840. Clamp only when the ratio itself is out of range. |
| MiniMax | Pass through when in the 8-value enum; else compute `width`/`height`. |

Never send `auto`. lith always resolves a concrete ratio, and `auto` would
discard that decision.

### Credentials — tiered lookup

Four tiers, highest first. The first tier that yields a usable credential wins;
lower tiers are not consulted.

| # | Source | Holds |
|---|---|---|
| 1 | **Shell environment** | `XAI_API_KEY` · `OPENAI_API_KEY` · `MINIMAX_API_KEY` |
| 2 | **`<repo>/.env`** | same variable names |
| 3 | **`~/.hermes/.env`** | same variable names |
| 4 | **`~/.hermes/auth.json`** | Hermes OAuth access tokens |

#### Variable names — exactly these, no aliases

| Provider | Variable | Notes |
|---|---|---|
| xAI | `XAI_API_KEY` | Also satisfied by tier 4's `xai-oauth` token. |
| OpenAI | `OPENAI_API_KEY` | Tier 4 cannot satisfy this — see the base-URL rules below. |
| MiniMax | `MINIMAX_API_KEY` | |

One name per provider. No `OPENAI_KEY`, no `GROK_API_KEY`, no fallback aliases:
a second accepted spelling means a typo silently resolves to "no key found" at
one tier and a stale value at another.

`OPENAI_ORG_ID` / `OPENAI_PROJECT_ID` are read only if present, and sent as
`OpenAI-Organization` / `OpenAI-Project`. Neither is required for
`/v1/images/generations`.

**Where to put a new key — tier 2 or tier 3 is a real choice.**

`~/.hermes/.env` is ingested by Hermes itself: `MINIMAX_API_KEY` lives there and
shows up in `auth.json` as a pool entry with `source: env:MINIMAX_API_KEY`. So a
key placed there becomes a Hermes credential too, not just a lith one.

`<repo>/.env` is scoped to lith and invisible to Hermes. Prefer it unless the
key is meant to be shared — smaller blast radius, and the repo is already
`.gitignore`d for `.env`, `.env.*`.

Shell beats every file, so a one-off `XAI_API_KEY=… lith-call …` always wins —
the standard dotenv/docker convention, and the behaviour least likely to
surprise. A repo `.env` pins the project; `~/.hermes/.env` is the user-global
default; `auth.json` is the last resort and the only tier lith does not own.

**Repo root discovery** walks upward from the recipe's directory when a recipe
is given, else from the cwd, stopping at the first `.git` or `pyproject.toml`.
Anchoring to the recipe rather than the cwd follows the same reasoning as
`paths.default_output_dir`: an agent's working directory is arbitrary.

#### Tier 4 rules — non-obvious and load-bearing

**Only `auth_type: oauth` entries carry a secret.** Measured on this install:
`api_key` entries store a `secret_fingerprint` and a `source` such as
`env:MINIMAX_API_KEY` — provenance, not the key. They are unusable and must be
skipped rather than treated as a hit.

**Validate `base_url` before using any token.** Matching on the provider name
alone will send the wrong credential to the wrong host. Accept a `credential_pool`
entry only when its `base_url` matches the provider's image API:

| Provider | Required `base_url` prefix |
|---|---|
| xAI | `https://api.x.ai/v1` |
| OpenAI | `https://api.openai.com/v1` |
| MiniMax | `https://api.minimax.io/v1` |

What that rejects on this machine, and why it matters:

| Pool entry | `base_url` | Verdict |
|---|---|---|
| `xai-oauth` | `https://api.x.ai/v1` | **usable** |
| `openai-codex` | `https://chatgpt.com/backend-api/codex` | reject — Codex backend, not the images API |
| `minimax-oauth` | `https://api.minimax.io/anthropic` | reject — Anthropic-compat chat shim |
| `minimax` | `https://api.minimax.io/anthropic` | reject — fingerprint only, no secret |

Without this check, an OpenAI request would be signed with a ChatGPT Codex token
and fail in a way that looks like a bad key.

**Refresh belongs to Hermes.** The `xai-oauth` entry carries a `refresh_token`
but no `expires_at_ms`, unlike `minimax-oauth` and `anthropic`. lith reads the
token at call time and, on a `401` from an OAuth-sourced credential, reports
"token expired — let Hermes refresh it" rather than running its own refresh and
racing Hermes for the same token file. lith never writes `auth.json`.

**Subscription quota is not API-credit quota.** A SuperGrok-backed OAuth token
may rate-limit differently from pay-as-you-go credits. Not a blocker; expect it
on long sweeps.

#### Handling

Both kinds become `Authorization: Bearer <secret>`; the header does not vary.
Only error handling does, per the refresh rule above.

Secrets are never logged, never placed in `raw`, never written to disk. A
missing credential raises naming the variable **and every tier searched**, so
the message is actionable rather than "no key found".

`lith-call --auth` prints, per provider, which tier resolved and a short
fingerprint — never a value. Same motivation as `--check`: make the decision
inspectable instead of a silent judgment.

### CLI

```
lith-call --recipe PATH [--out DIR] [--n N] [--resolution 1k|2k]
          [--quality low|medium|high] [--seed N] [--dry-run] [--emit-json]
lith-call --check --recipe PATH        # routing decision only, no call
```

`--dry-run` prints the exact request body per provider, keys redacted. Given
this project's history, seeing the payload without spending money is worth more
than any other flag here.

Candidates land as `{stem}-c{i}.{ext}`, extension from magic bytes, never from
the model id. Publishing stays with `lith-run`, which owns the frame check.

### Hermes routing

Use `image_generate` only when **both** hold:

1. the Hermes active model (`config.yaml` → `image_gen.model`, else
   `FAL_IMAGE_MODEL`) equals the recipe's `model`, and
2. the envelope's resolved `aspect_ratio` is one of `16:9`, `1:1`, `9:16`

Otherwise call `lith-call`. The second condition matters as much as the first:
`image_generate` accepts three buckets, so a matching model still delivers the
wrong frame for `2:3`, `3:2` or `20:9`. `lith-call --check` prints this decision
and its reason so routing is inspectable, not a silent judgment each run.

---

## 5. Task graph

### Phase 0 — realign lith with the docs

> No provider calls. Every task here is `OFFLINE` and safe for any agent.
> `P0-1` gates most of the phase; `P0-5` and `P0-8` are independent and may
> start immediately.

**`P0-1` — Capability record type**
Needs: — · Env: `OFFLINE` · Files: `src/lith/aspect.py`, `tests/test_lith_render.py`
Replace `MODEL_ASPECTS: dict[str, set[str]]` with a record expressing three
variants: ratio enum, fixed pixel-size list, constrained range (§2.2). Carry
`n_max` and `prompt_max_chars` per model (§3.3). Keep `resolve_aspect`'s
`(aspect, note)` return signature unchanged so `render.py` is untouched.
Done: all three variants representable; existing suite green.

**`P0-2` — Correct every entry**
Needs: `P0-1` · Env: `OFFLINE` · Files: `src/lith/aspect.py`
grok 2.0 gains `9:19.5`, `19.5:9`, `auto`. Add `gpt-image-1.5`,
`gpt-image-1-mini` (gpt-image-1's three sizes), `gpt-image-2-2026-04-21`.
Retain the callable previous-generation `grok-imagine-image-quality` and
`grok-imagine-image` entries at their existing 9-value ratio enum; removing
them makes the pinned live recipe and Hermes' configured model unroutable.
Replace `minimax-image` with `image-01` at its 8-value enum plus
`prompt_max_chars=1500`, `n_max=9`. **Skip `image-01-live`** — i2i only, and i2i
is out of scope (§6). `gpt-image-1` is already correct; do not change it.
Done: every value traces to a §2 line; a test asserts each model's entry against
a literal transcribed from §2.

**`P0-3` — Range-aware clamping**
Needs: `P0-1` · Env: `OFFLINE` · Files: `src/lith/aspect.py`
`nearest_supported` returns the input unchanged when a range admits it;
`unsupported_aspect` stops warning about ratios gpt-image-2 can produce.
Done: `gpt-image-2` at `20:9` resolves unclamped with no note; `gpt-image-1` at
`16:9` still clamps to `3:2` with its note.

**`P0-4` — `aspect.pixel_size(model, aspect) -> str`**
Needs: `P0-1` · Env: `OFFLINE` · Files: `src/lith/aspect.py`
Ratio → `"WIDTHxHEIGHT"`. For 1.x models a lookup; for gpt-image-2 a search
satisfying ÷16, ratio range, pixel budget, edge ≤ 3840. Pure, no network.
Done: property test over the full ratio enum — every result satisfies all four
constraints and its ratio is within 1% of the request, or raises explaining why
the ratio is unreachable.

**`P0-5` — Extract `imagebytes.py`**
Needs: — · Env: `OFFLINE` · Files: `src/lith/imagebytes.py` (new),
`src/lith/cli/run.py`, `tests/test_lith_cli_run.py`
Move `download`, `looks_like_image`, `image_ext`, `image_size`. Leave
`aspect_mismatch` in `cli/run.py` — it is a CLI policy, not a byte utility.
Pure move; no behaviour change.
Done: `cli/run.py` imports from `lith.imagebytes`; suite green with no test
rewritten beyond the import path.

**`P0-6` — Purity guard test**
Needs: `P0-5` · Env: `OFFLINE` · Files: `tests/test_lith_layering.py` (new)
Assert `render`, `aspect`, `layout`, `recipe`, `styles`, `paths` import neither
`lith.cli` nor `lith.call`, and reference no network symbol.
Done: test fails if a future change makes a pure module network-aware.

**`P0-7` — Validate `n` and prompt length**
Needs: `P0-2` · Env: `OFFLINE` · Files: `src/lith/aspect.py` or a new
`limits.py`, `src/lith/cli/generate.py`
Emit a note when `recipe.n` exceeds the model's `n_max`, and when the rendered
prompt exceeds `prompt_max_chars` — surfaced like `aspect_note`/`copy_note` and
carried in the envelope.
Done: any testbed recipe pinned to `image-01` warns on prompt length; `--n 12`
on an xAI model warns.

**`P0-8` — Refresh CLI choices**
Needs: — · Env: `OFFLINE` · Files: `src/lith/cli/generate.py`
`--model` choices to the real ids. `--aspect` choices currently omit ratios
every provider supports; widen from the union of §2 enums.
Done: `--model image-01` and `--aspect 20:9` accepted.

**`P0-9` — Testbed rows**
Needs: `P0-2` · Env: `OFFLINE` · Files: `recipes/integration/*.json`,
`tests/test_integration_recipes.py`
Rows pinned to `minimax-image` move to `image-01`. Add a `gpt-image-2` row at a
ratio outside the old 15 (e.g. `20:9`) that must now resolve unclamped.
Done: coverage assertions still pass; the new row resolves with no note.

**`P0-10` — `negative_prompt` policy**
Needs: — · Env: `OFFLINE` · Files: `docs/explanation-pipeline.md`,
`skills/lith/SKILL.md`
Keep the field — FAL/Flux backends accept one. Never send where unsupported,
always report in `CallResult.unsupported`, never concatenate into `prompt`.
Done: documented in both files.

**Phase 0 acceptance:** every capability value traces to a cited doc line;
`gpt-image-2` at `20:9` resolves unclamped; `gpt-image-1` at `16:9` still
clamps; the suite passes with no network access.

### Phase 1 — the layer, xAI only

**`P1-1` — `creds.py`, tiered lookup**
Needs: — · Env: `OFFLINE` · Files: `src/lith/call/creds.py`, `.gitignore`,
`tests/test_lith_creds.py` (new)

Implement the four tiers in §4 — shell → `<repo>/.env` → `~/.hermes/.env` →
`~/.hermes/auth.json`.

`.gitignore` already covers `.env`, `.env.*` (added ahead of this task, since a
key was about to be placed there). Add `.env.example` listing the three variable
names with empty values, as the discoverable record of what lith looks for.

Tier 4 must skip `auth_type: api_key` entries (fingerprint only, no secret) and
must reject any entry whose `base_url` does not match the provider's image API
prefix. Never write `auth.json`.

Done: tests cover each tier winning in turn with the tiers above it absent; a
shell value beating a repo `.env`; an `api_key` pool entry being skipped; a
`base_url` mismatch being rejected (use the real `openai-codex` shape —
`https://chatgpt.com/backend-api/codex` — as the fixture); and a missing-key
error naming all four tiers. No test may read the developer's real
`~/.hermes/`; point at a temp `HOME`.

**`P1-2` — `http.py`**
Needs: `P0-5` · Env: `OFFLINE` · Files: `src/lith/call/http.py`
POST-JSON over `urllib`, timeout, one retry on 429/5xx with backoff, a typed
error hierarchy (`AuthError`, `RateLimited`, `ContentRejected`,
`InvalidRequest`, `ProviderError`). Redact `Authorization` from anything
rendered.
Done: fixture tests map each provider's failure shape — including MiniMax's
`base_resp.status_code` inside a `200` — to the right exception.

**`P1-3` — Types and dispatcher**
Needs: `P0-4`, `P1-2` · Env: `OFFLINE` · Files: `src/lith/call/__init__.py`,
`src/lith/call/capability.py`
`ImageRequest`, `Candidate`, `CallResult`, `generate()`, model → provider map.
Done: `generate()` dispatches on model id and raises a clear error for unknown
ids.

**`P1-4` — `xai.py`**
Needs: `P1-3` · Env: `OFFLINE` (fixtures) · Files: `src/lith/call/xai.py`
Request build, `response_format=b64_json` explicitly (avoids a second fetch and
URL expiry), `n` 1–10, `resolution`, `revised_prompt` capture,
`negative_prompt` → `unsupported`.
Done: fixture test asserts the exact request body and a parsed `CallResult`.

**`P1-5` — `lith-call` CLI**
Needs: `P1-4` · Env: `OFFLINE` · Files: `src/lith/cli/call.py`, `pyproject.toml`
`--dry-run`, `--emit-json`, `--check`, per-candidate output paths.
Done: `--dry-run` prints the request body with keys redacted; `--check` prints
the Hermes-vs-`lith-call` routing decision and its reason.

**`P1-6` — First live call**
Needs: `P1-5` · Env: `KEY:xai` · Files: —
Done: one call at `aspect_ratio: "2:3"`, `n: 2` returns two candidates at
~0.667, `lith-run --strict` exits 0 on both, and `CallResult.model_reported`
names the id that actually served. **This single result closes what two sweeps
and 68 generations could not.**

### Phase 2 — OpenAI and MiniMax

**`P2-1` — `openai.py`**
Needs: `P1-4` · Env: `OFFLINE` · Files: `src/lith/call/openai.py`
`pixel_size` mapping, `quality`, `background`, `output_format`,
`output_compression`, `moderation`, `n` 1–10.
Done: fixture tests for a 1.x model and gpt-image-2 show different `size`
strategies from the same `ImageRequest`.

**`P2-2` — `minimax.py`**
Needs: `P1-4`, `P0-7` · Env: `OFFLINE` · Files: `src/lith/call/minimax.py`
`n` 1–9 batched, `prompt_optimizer`, `seed`, width/height fallback,
`base_resp.status_code` → typed errors. **Raise before the call when the prompt
exceeds 1500 chars** (§3.1) rather than letting the provider reject it.
Done: a testbed recipe raises the precondition error with the measured length
and the cap, naming §3.1 as the reason.

**`P2-3` — Live cross-provider check**
Needs: `P2-1` · Env: `KEY:openai` · Files: —
Done: the same recipe renders on xAI and OpenAI; `gpt-image-2` returns the exact
requested ratio; `gpt-image-1` returns the clamped one with its note.

### Phase 3 — exploit what is unique

**`P3-1` — `resolution: 2k` experiment**
Needs: `P1-6` · Env: `KEY:xai`
**Highest-value experiment available.** Re-run the dense rows (03, 07, 13, 18)
at `2k` and compare copy fidelity against the `1k` baseline. Settles whether
panel area is the copy-fidelity variable — the one finding that survived both
sweeps. Needs one flag.

Measured 2026-08-16 with `grok-imagine-image-2.0`, one candidate per request:

| row | 1k pixels | 2k pixels | copy-fidelity result |
| --- | --- | --- | --- |
| 03 | 1248×832 | 2496×1664 | Authored copy was exact at both sizes; no material fidelity change. |
| 07 | 1248×832 | 2496×1664 | 1k leaked style instructions into the title and misspelled the subtitle; 2k rendered the authored title and subtitle exactly. |
| 13 | 832×1248 | 1664×2496 | Authored copy was exact at both sizes; no material fidelity change. |
| 18 | 832×1248 | 1664×2496 | Authored copy was exact at both sizes; no material fidelity change. |

Result: 2k materially improved the one failing dense row (07), while the other
three rows were already copy-faithful at 1k. Panel area can fix a fidelity
failure, but this sample does not support it as the sole or universal variable.

**`P3-2` — Exact-ratio rendering**
Needs: `P2-3` · Env: `KEY:openai`
gpt-image-2 is the only provider that renders `20:9` as `20:9` rather than the
nearest listed neighbour — the frame the layout was actually composed for.

**`P3-3` — xAI `storage_options`**
Needs: `P1-6` · Env: `KEY:xai`
Stable public URLs instead of expiring ones.

Measured 2026-08-16: one request with `filename`, `public_url: true`, and the
maximum `expires_after: 2592000` returned one 832×1248 candidate,
`storage_error: null`, and a `file_output.public_url` on `files-cdn.x.ai` with
no query string. The ordinary `data[].url` remained on the temporary
`imgen.x.ai` host. The adapter therefore prefers and fetches the stored public
URL while preserving both values in `CallResult.raw`. The public object lasts
for the requested 30 days; the provider does not offer a permanent lifetime.

**`P3-4` — OpenAI extras**
Needs: `P2-3` · Env: `KEY:openai`
`quality` sweep; `background: transparent` for overlay use; `output_format:
webp` with compression for smaller artifacts.

### Phase 4 — skill and docs

**`P4-1`** Needs: `P1-5` · Env: `OFFLINE` · `skills/lith/SKILL.md` — routing
rule, `lith-call` usage, `--check` before any sweep.
**`P4-2`** Needs: `P2-2` · Env: `OFFLINE` · `README.md`,
`docs/reference-python-api.md` — CLI reference, `lith.call` section, new
capability type and `pixel_size`.
**`P4-3`** Needs: `P2-3`, `P4-1` · Env: `KEY:xai`+`KEY:openai` — rerun the
34-recipe testbed through `lith-call`, all live ids, publishing via
`lith-run --strict`.

---

## 6. Out of scope — decided, do not build

**MiniMax image-to-image.** `subject_reference` takes `type: "character"` only,
one image, a front-facing portrait. It holds a person's likeness steady across a
series. lith renders dense text posters; there is no face in one. Do not
implement `subject_reference`, and do not register `image-01-live`. Revisit only
if a style family gains a recurring character — and note that "MiniMax i2i
support" would then mean portrait references, never poster editing.

**Billing.** `CallResult.cost` passes through what the provider reports — xAI's
`usage.cost_in_usd_ticks`, nothing from the other two. No estimation, no
budgeting, no caps.

**MiniMax stays wired; templates stay full.** Keep the adapter behind its
1500-character precondition, but do not compact the seven templates. The
compressible mass is the anti-invention machinery; removing it would create a
second visual identity per family for a provider whose only unique parameter is
`seed`. Keep `prompt_optimizer: false` permanently: its mechanism is
undocumented, it modifies a prompt containing the literal copy block, and it
cannot be scoped to leave the SPEC block alone.

**Video, candidate scoring, post ingestion.** Unchanged from
`docs/explanation-pipeline.md` § Deliberate omissions.

---

## 7. Open questions

**`Q-1` — xAI edits: `mask`, `n`, `aspect_ratio`, `resolution`.**
Blocks: any i2i work. Env: `KEY:xai`.

The endpoint's own parameter table omits `model` and `image`, which provably
work, so absence proves nothing and only a probe can answer it.

`mask` decides whether the endpoint is useful. The repair case is a poster where
forty lines are correct and one panel is garbled — with a mask that is a
surgical fix; without one the model reinterprets the whole frame from a text
instruction and re-rolls copy that was already right. OpenAI documents `mask` on
its edits endpoint, so if masked repair matters, that is the known-good path and
xAI is the unknown.

Probe: one call with a known-good poster plus `mask` and `n: 2`. Three outcomes,
all informative — rejects the unknown fields (well-behaved), honours them (edits
are viable), or accepts and ignores them, in which case this endpoint earns the
same suspicion as the Hermes bridge. **Distinguishing *unsupported* from
*silently ignored* is the actual goal.**

Resolved by one probe on 2026-08-16. One JSON request sent a known-good
832×1248 poster, a same-size alpha mask covering only the footer, `n: 2`,
`aspect_ratio: "2:3"`, and `resolution: "1k"`. The endpoint accepted every
field and returned two 832×1248 candidates from the single request. Both
changed the masked footer from `s11a.com` to `Q1 PROBE` while preserving the
visible layout and copy outside the mask. In this probe, `mask`, `n`,
`aspect_ratio`, and `resolution` were honoured rather than silently ignored.
