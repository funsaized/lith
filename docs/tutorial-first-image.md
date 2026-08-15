# Tutorial: your first announcement image

In this tutorial we will take a one-sentence announcement — *"Hermes Agent now
supports 32 new languages"* — and turn it into a finished 16:9 image, using the
pipeline end to end.

By the end we will have produced this file:

```
outputs/B_brutalist_32_langs.jpg
```

A black sci-fi-brutalist panel with a `32 LANGS` headline.

We will do it in five moves: install, render a prompt, save a recipe, bring in a
generated image, and publish it. Every command here is meant to run exactly as
written.

---

## Step 1 — Install the pipeline

From the repository root:

```bash
uv sync --extra test
```

That is the whole install — lith is standard library only, with no binaries to
put on `$PATH`. Now check that the pipeline is wired up:

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
[output]      .../outputs/B_brutalist_32_langs.<jpg|png|webp>
```

Four flags became a full prompt, a negative prompt, and an output path. Notice
that our headline was placed *inside* the prompt, and that the output filename
was derived from the style family plus the headline.

The extension is left open. No image exists yet, so neither command guesses a
format — the file we publish in step 5 is named after the bytes that arrive.

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
[output]      .../outputs/B_brutalist_32_langs.<jpg|png|webp>
Next: call image_generate with the prompt, then re-run with --image-url or --image-file.
```

With no image supplied, the driver prints its plan and stops. This is the safe
dry run — we can call it as often as we like while tuning a brief. The
extension is left open because the driver names the file after the bytes the
model actually returns.

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

Open it. It has the black panel, the grid, the globe silhouette, and the
headline the model rendered from our prompt.

---

## Step 5 — Publish it

Now we run the driver for real, handing it that image:

```bash
uv run lith-run \
  --recipe recipes/tutorial_first_post.json \
  --image-file outputs/B_brutalist_32_langs_raw.jpg
```

```
[copy]        outputs/B_brutalist_32_langs_raw.jpg
[done]        .../outputs/B_brutalist_32_langs.jpg
```

The driver checked the file's magic bytes, saw JPEG, and published it under the
name the recipe derives — `.jpg`, because that is what the bytes are. Nothing
was re-encoded: the published file is byte-identical to the one we fed in. Open
`outputs/B_brutalist_32_langs.jpg` and it matches.

Re-run the same command and it lands on the same path again. The output name is
a function of the recipe, so a second run overwrites the first rather than
leaving us to guess which file is current.

---

## What we did

We turned a sentence into a finished graphic:

1. `lith-generate` rendered our brief into a style-locked prompt.
2. A recipe file made that brief repeatable.
3. `lith-run` dry-ran the plan, then validated and published a generated image.

## Where to go next

- The other six style families and when to use each —
  [README → Style families](../README.md#style-families).
- Why the families exist, how a prompt is put together, and the failure modes
  to watch for — [About the design language](explanation-design-language.md).
- Why the driver never calls a model itself —
  [About the pipeline](explanation-pipeline.md).
- Writing a dense poster spec — headline, subtitle, sections, diagram, footer —
  for a family that renders all of it: [README → Recipe format](../README.md#recipe-format).
- Full CLI flags for both entry points, including `--image-url` and
  `--output-dir` — [README → CLI reference](../README.md#cli-reference).
