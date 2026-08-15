# Tutorial: your first announcement image

In this tutorial we will take a one-sentence announcement — *"Hermes Agent now
supports 32 new languages"* — and turn it into a finished 16:9 PNG with
pixel-perfect overlay copy, using the pipeline end to end.

By the end we will have produced this file:

```
outputs/B_brutalist_32_langs.png
```

A black sci-fi-brutalist panel with a `32 LANGS` headline and three cyan status
lines under it.

We will do it in five moves: install, render a prompt, save a recipe, bring in a
generated image, and overlay the copy. Every command here is meant to run
exactly as written.

---

## Step 1 — Install the pipeline

From the repository root:

```bash
uv sync --extra test
```

We also need ImageMagick for the final step:

```bash
brew install imagemagick
magick --version
```

Now check that the pipeline is wired up:

```bash
uv run lith-generate \
  --topic "test" --style B --aspect 16:9 --headline "32 LANGS" --icon "globe"
```

A block of prompt text prints and the command exits. We're ready.

---

## Step 2 — Render our first prompt

The pipeline never asks a model to invent a look. It renders our brief into one
of seven fixed style families. We'll use family **B — sci-fi brutalist UI**.

```bash
uv run lith-generate \
  --topic "Hermes Agent now supports 32 new languages" \
  --style B \
  --aspect 16:9 \
  --headline "32 LANGS" \
  --icon "globe"
```

We get back something like:

```
[style]       Sci-fi brutalist UI
[aspect]      16:9
[prompt]
  Single black panel, 16:9. Center-aligned massive HUD-style text. Background:
  pure black #000000 with a 1px cyan grid line at 8% opacity. Headline:
  '32 LANGS' in 180px monospaced all-caps ...
[negative]    pastel, soft, organic, photographic, gradient backgrounds, ...
[output]      .../outputs/B_brutalist_32_langs.png
```

Four flags became a full prompt, a negative prompt, and an output path. Notice
that our headline was placed *inside* the prompt, and that the output filename
was derived from the style family plus the headline.

---

## Step 3 — Save the brief as a recipe

Flags are fine for one-offs. Anything we want to re-run belongs in a recipe
file. Create `recipes/tutorial_first_post.json`:

```json
{
  "name": "tutorial_first_post",
  "description": "Tutorial recipe: sci-fi brutalist announcement for the 32-language release.",
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

Now ask the driver what it intends to do with that recipe:

```bash
uv run lith-run --recipe recipes/tutorial_first_post.json
```

```
[recipe]      recipes/tutorial_first_post.json
[family]      B_brutalist
[style]       Sci-fi brutalist UI
[aspect]      16:9
[model]       grok-imagine-image-quality (n=4)
[prompt]
  Single black panel, 16:9. ...
[output]      .../outputs/B_brutalist_32_langs.png
Next: call image_generate with the prompt, then re-run with --image-url or --image-file.
```

With no image supplied, the driver prints its plan and stops. This is the safe
dry run — we can call it as often as we like while tuning a brief.

---

## Step 4 — Get a generated image

The driver does not call an image model itself; we hand it one. To send this
prompt to a model, emit the machine-readable envelope:

```bash
uv run lith-generate \
  --recipe recipes/tutorial_first_post.json \
  --call --emit-json
```

That JSON carries `prompt`, `negative_prompt`, `aspect_ratio`, `model`, `n`, and
`seed` — everything an image-generation tool needs. Pass it to Grok (or to a
Hermes session), pick the best of the four candidates, and keep its URL.

We don't need a model to finish this tutorial. The repository ships a real Grok
result from this exact prompt, so we'll use it as our generated image:

```
outputs/B_brutalist_32_langs_raw.jpg
```

Open it. It has the black panel, the grid, the globe silhouette, and a headline
the model rendered on its own. What it does *not* have is trustworthy small
text — which is exactly what the last step is for.

---

## Step 5 — Overlay the copy and finish

Now we run the driver for real, feeding it that image and the three literal
lines we want rendered in our own font:

```bash
uv run lith-run \
  --recipe recipes/tutorial_first_post.json \
  --image-file outputs/B_brutalist_32_langs_raw.jpg \
  --line SYSTEM='32 language runtimes online' \
  --line NEW='Full-stack · AI · MLOps' \
  --line READY='One agent. Every stack.'
```

```
[copy]        outputs/B_brutalist_32_langs_raw.jpg -> .../outputs/B_brutalist_32_langs_raw.jpg
.../outputs/B_brutalist_32_langs.png
[done]        .../outputs/B_brutalist_32_langs.png
```

Open `outputs/B_brutalist_32_langs.png`. Each `--line LABEL=copy` became a row:
the label in red brackets, the copy in cyan, both in Menlo at a fixed size and
position. Nothing there was hallucinated — every character is ours.

Compare it against `outputs/B_brutalist_32_langs_verified.png`, the reference
artifact committed to this repo. They should look the same. We just reproduced
it.

---

## Step 6 — Change something and re-run

Let's confirm we own that copy. Re-run with a different third line:

```bash
uv run lith-run \
  --recipe recipes/tutorial_first_post.json \
  --image-file outputs/B_brutalist_32_langs_raw.jpg \
  --line SYSTEM='32 language runtimes online' \
  --line NEW='Full-stack · AI · MLOps' \
  --line READY='Ship in any language.'
```

Open the PNG again — the third line changed, and we never re-generated the
image. Overlay copy is cheap; generation is not. That separation is the point
of the pipeline.

---

## What we did

We turned a sentence into a finished graphic:

1. `lith-generate` rendered our brief into a style-locked prompt.
2. A recipe file made that brief repeatable.
3. `lith-run` dry-ran the plan, then ingested a generated image.
4. `--line` overlaid literal copy in our own font, deterministically.

## Where to go next

- The other six style families, their prompt recipes, and when to use each —
  [README §1 and §3](../README.md#1-the-seven-style-families).
- The six required prompt slots every brief fills —
  [README §4](../README.md#4-the-non-negotiable-prompt-anatomy).
- Full CLI flags for both entry points, including `--image-url`, `--font`, and
  `--output-dir` — [README §8](../README.md#8-usage).
- The failure modes to watch for (model typography, the "AI gradient" trap) —
  [README §9](../README.md#9-pitfalls).
