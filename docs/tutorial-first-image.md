# Tutorial: your first announcement image

In this tutorial we will turn an announcement — *"Hermes Agent now runs 32
language runtimes"* — into a finished poster: a title, three labelled panels of
copy we write ourselves, and a footer.

By the end we will have produced this file:

```
outputs/B_brutalist_32_langs.jpg
```

We will do it in six moves: install, write a recipe, change its layout, inspect
the model call, generate, and publish. Every command here is meant to run
exactly as written. Only step 5 can spend money, and it has a free path.

---

## Step 1 — Install the pipeline

From the repository root:

```bash
uv sync --extra test
```

That is the whole install — lith is standard library only, with no binaries to
put on `$PATH`. Check that it is wired up:

```bash
uv run lith-generate --topic "test" --style B --headline "HELLO"
```

A block of prompt text prints and the command exits. We're ready.

---

## Step 2 — Write a recipe

A recipe holds every word that will appear in the image. Create
`recipes/tutorial_mesh.json`:

```json
{
  "name": "tutorial_mesh",
  "description": "Tutorial recipe: a three-panel explainer in the sci-fi brutalist family.",
  "style": "B",
  "model": "grok-imagine-image-2.0",
  "n": 4,
  "brief": {
    "topic": "Hermes Agent now runs 32 language runtimes",
    "headline": "32 LANGS",
    "subtitle": "ONE AGENT, EVERY STACK",
    "icon": "globe",
    "sections": [
      {"heading": "01 - RUNTIMES", "lines": [
        "32 languages, one image",
        "Python, Go, Rust, Zig",
        "No per-project setup"]},
      {"heading": "02 - THE SANDBOX", "lines": [
        "Each run is isolated",
        "Network off by default"]},
      {"heading": "03 - THE RESULT", "lines": [
        "Ship in any stack",
        "One agent, every repo"]}
    ],
    "footer": "hermes.dev"
  }
}
```

Ask the driver what it intends to do with it:

```bash
uv run lith-plate --recipe recipes/tutorial_mesh.json
```

```
[recipe]      recipes/tutorial_mesh.json
[family]      B_brutalist
[style]       Sci-fi brutalist UI
[aspect]      2:3
[model]       grok-imagine-image-2.0 (n=4)
[prompt]
  Single pure-black panel (#000000) overlaid with a 1px cyan grid at 8% opacity...
  LAYOUT — arrange the frame exactly as these numbered notes describe...
  (1) the title, set at 12-15% of frame height, with the subtitle centred beneath it...
  (2) the 3 section panels, with the first panel spanning the full width at roughly
      double height as the anchor of the composition, and the rest in a balanced grid
      beneath it...
  (3) the footer line, on a rule beneath everything else.
  ...
  TITLE: 32 LANGS
  SUBTITLE: ONE AGENT, EVERY STACK
  SECTION 1 HEADING: 01 - RUNTIMES
      - 32 languages, one image
  ...
[output]      .../outputs/B_brutalist_32_langs.<jpg|png|webp>
```

Three things happened that we never asked for.

The aspect came out **2:3**, though our recipe never mentions one. Three panels
of copy need vertical room, so lith chose a portrait frame.

The panels were arranged as a **hero** — one wide panel anchoring the top, the
other two beneath. That also came from the panel count and the frame.

And every word we wrote appears at the bottom of the prompt under a standing
order to reproduce it character for character. The model draws; it never
authors.

With no image supplied the driver prints its plan and stops. This is the safe
dry run, and we can call it as often as we like.

---

## Step 3 — Change the layout

We are not stuck with what lith derived. Add one key to the brief:

```json
    "layout": "timeline",
```

Run the same dry run again and watch zone (2) change:

```
  (2) the 3 section panels, as a top-to-bottom sequence joined by one continuous
      vertical spine, each panel connected to the spine by a short horizontal stub
      and set slightly further right than the one above it, ...
```

Our three numbered steps now read as a sequence rather than a hero block, and
nothing else about the prompt moved. Try `radial`, `masonry`, or `split` and
run it again — [fifteen arrangements](explanation-layouts.md) are available.

Set it back to `hero` (or delete the line) before continuing.

---

## Step 4 — Look at the call before making it

`lith-call` is the command that reaches a provider. Before it spends anything,
ask it which road it plans to take:

```bash
uv run lith-call --check --recipe recipes/tutorial_mesh.json
```

```
route=lith-call
reason=Hermes active model '...' does not match recipe model
       'grok-imagine-image-2.0'; Hermes image_generate cannot preserve resolved
       aspect '2:3'; it routes only 16:9, 1:1, 9:16
```

Your `reason` will name whatever model your Hermes install has configured. The
`route` is what matters: when Hermes' tool cannot deliver the exact model *and*
the exact frame, lith calls the provider directly.

Now look at the request itself, still without touching the network:

```bash
uv run lith-call --dry-run --recipe recipes/tutorial_mesh.json
```

```json
{
  "provider": "xai",
  "method": "POST",
  "url": "https://api.x.ai/v1/images/generations",
  "headers": {
    "Authorization": "Bearer <redacted>"
  },
  "body": {
    "model": "grok-imagine-image-2.0",
    "prompt": "Single pure-black panel (#000000) overlaid with …",
    "n": 4,
    "aspect_ratio": "2:3",
    "response_format": "b64_json"
  },
  "unsupported": {
    "negative_prompt": "xAI image generation does not accept negative_prompt"
  }
}
```

This is the exact JSON that would go over the wire, with the credential
redacted. Two things are worth noticing.

The `aspect_ratio` is `2:3` — the frame lith derived in step 2, sent verbatim
rather than rounded to something the provider finds convenient.

And `unsupported` names a field xAI cannot accept. Lith reports it instead of
folding it into `prompt`, because text smuggled into a prompt is text the model
can letter into the image.

---

## Step 5 — Generate

If you have a provider key, make the call:

```bash
uv run lith-call --recipe recipes/tutorial_mesh.json --n 1
```

```
[done]        .../outputs/B_brutalist_32_langs-c0.jpg
[model_reported] grok-imagine-image-2.0
[unsupported] negative_prompt: xAI image generation does not accept negative_prompt
```

`model_reported` is the id the provider says actually served the request — not
the one we asked for. When those differ, we want to know.

**No key? We can still finish.** The repository ships a real Grok result from
this family, so use it as our generated image:

```
outputs/B_brutalist_32_langs_raw.jpg
```

Either way we now hold a generated image. Lith did not pick it for us; choosing
among candidates is our job.

---

## Step 6 — Publish it

Hand the image to the driver:

```bash
uv run lith-plate \
  --recipe recipes/tutorial_mesh.json \
  --image-file outputs/B_brutalist_32_langs_raw.jpg
```

```
[copy]        outputs/B_brutalist_32_langs_raw.jpg
[warn]        aspect: requested 2:3 (0.667), received 1280x720 (1.778)
[done]        .../outputs/B_brutalist_32_langs.jpg
```

The driver read the file's magic bytes, saw JPEG, and published it as `.jpg` —
the extension follows the bytes, not the recipe. Nothing was re-encoded: the
published file is byte-identical to the one we fed in.

That `[warn]` is the driver doing its job. It measured the image, got 16:9, and
compared it against the `2:3` our recipe asked for. The shipped sample was
generated for a different recipe, so the mismatch is real and lith says so —
the layout in our prompt was composed for a portrait frame.

Add `--strict` and that warning becomes an exit code:

```bash
uv run lith-plate --recipe recipes/tutorial_mesh.json \
  --image-file outputs/B_brutalist_32_langs_raw.jpg --strict
echo $?          # 1
```

The file still publishes — the bytes are the evidence you need to see *how* the
frame differs. Use `--strict` in any batch, where a warning would scroll past
unread. On an image that really came from step 5, it exits `0`.

Re-run the same command and it lands on the same path again. The output name is
a function of the recipe, so a second run overwrites the first rather than
leaving us to guess which file is current.

---

## What we did

We turned an announcement into a finished graphic:

1. A recipe held every word that would appear in the image.
2. `lith-plate` dry-ran the plan, choosing a frame and an arrangement from the
   shape of our content.
3. One key changed the arrangement without touching anything else.
4. `lith-call --check` and `--dry-run` showed the route and the exact request
   before anything was spent.
5. `lith-call` generated candidates, reporting which model really served them.
6. `lith-plate` checked the delivered frame against the request and published
   under a derived name.

## Where to go next

- The fifteen arrangements and when each one earns its place —
  [About layouts](explanation-layouts.md).
- How the same recipe looks in each of the seven families —
  [About output styles](explanation-output-styles.md).
- Why the copy is written down first, and why lith now makes the call itself —
  [About the pipeline](explanation-pipeline.md).
- The palette, typography and composition rules the families share —
  [About the design language](explanation-design-language.md).
- Every brief key, flag, and return shape —
  [README → Recipe format](../README.md#recipe-format) and the
  [Python API reference](reference-python-api.md).
