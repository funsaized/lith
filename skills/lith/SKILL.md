---
name: lith
description: Generate tech images through seven style families.
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
seven style families. Let the package handle deterministic prompt rendering,
recipe loading, and output paths. Use the active session for image generation
and optional topic expansion.

## When to use

- Generate an image for a post, announcement, or feature.
- Work with one of the seven style families A-G.
- Expand a topic into a complete image brief.

## Prerequisites

- Install the CLI tools with
  `uv tool install git+https://github.com/funsaized/lith`.
- Add lith to the current Python environment before using the in-process API.

## Workflow

1. Render the recipe and obtain the model-call envelope:

   ```bash
   lith-generate --recipe /absolute/path/to/recipe.json --call --emit-json
   ```

2. Call the available image-generation tool with `prompt`, `aspect_ratio`,
   `model`, `n`, and any other envelope fields that provider supports. Keep
   `negative_prompt` in the envelope because FAL/Flux backends accept it. When
   the selected provider does not, do not send it: preserve `prompt` verbatim
   and require the adapter to record `negative_prompt` and the reason in
   `CallResult.unsupported`. Ask the user to choose when multiple candidates
   require subjective selection.

3. Pass the chosen HTTP(S) image URL to the driver, which validates it and
   publishes it under the recipe's deterministic output path:

   ```bash
   lith-run --recipe /absolute/path/to/recipe.json --image-url <url> --strict
   ```

   The published extension follows the returned bytes (`.jpg`, `.png`, or
   `.webp`); the image is never re-encoded.

   Never write the model's bytes to disk any other way. `lith-run` is the only
   step that checks the delivered frame against the one the prompt was composed
   for, and a generation tool may quietly substitute a different one. Add
   `--strict` in any batch or sweep so a substituted frame exits 1 instead of
   printing a warning that scrolls past.

4. Use `--image-file /absolute/path/to/image` instead of `--image-url` for a
   local source.

Use the library directly when lith is installed in the active Python
environment:

```python
from lith import load_recipe, render_prompt

recipe = load_recipe("/absolute/path/to/recipe.json")
rendered = render_prompt(recipe)
```

## Writing the brief

All seven families render a dense poster from the same spec. Give the brief
the full copy — every word is printed into the image verbatim:

```json
{
  "topic": "private tailscale mesh across three machines",
  "headline": "TAILSCALE",
  "icon": "lightning",
  "aspect": "2:3",
  "subtitle": "A PRIVATE CLOUD IN THREE MACHINES",
  "sections": [
    {"heading": "01 - THE HUB", "lines": ["Mac mini M4, always on", "mosh survives every dropped link"]}
  ],
  "diagram": "A central cloud labeled TAILSCALE with lines to boxes MINI, AIR and NZXT",
  "footer": "s11a.com",
  "base_color": "#FFD700"
}
```

`topic`, `headline` and `icon` are required on every brief — a recipe missing
any of them fails to load. Everything else, `aspect` included, is optional.

Use 3-5 sections of 2-4 lines each, every line under 9 words and concrete —
real names, numbers, commands, never filler. Keep total body copy to 60-140
words. Set `base_color` whenever the family palette lists several backgrounds.

Omit `layout` unless the content has a shape worth naming: `timeline` for
ordered steps, `radial` for a hub with satellites, `split` for a comparison,
`hero` when one section outranks the rest, `masonry` or `zigzag` when the piece
should read as editorial rather than tabular. Otherwise lith derives a grid from
the section count and the frame. `diagram` is drawn, not lettered — only the
labels it names appear as text.

## Conventions

- Keep headlines to 1-3 all-caps, ASCII-friendly words.
- Omit `aspect` unless the user asked for a specific shape. Lith picks it from
  the content — three or more sections go portrait — then clamps it to what the
  recipe's model can produce, and prints a warning on stderr when it substitutes.
- Let the image model render the copy the spec supplies. Fix a wrong line by
  correcting the brief and re-generating, never by editing the image.
- Do not publish, post, or upload unless the user separately authorizes it.

## Pitfalls

- Treat recipe `n` as the requested candidate count and select one candidate
  manually.
- Report which of `prompt`, `negative_prompt`, `aspect_ratio`, `model` and `n`
  the generation tool actually accepted. A tool that ignores a field still
  returns an image, so a run can look clean while the envelope was discarded.
- Never concatenate, prepend, or append an envelope field to the `prompt`
  string when the provider has no parameter for it. A negative prompt pasted
  into a positive prompt asks the model *for* what it was meant to forbid, and
  every smuggled line is more text the model can letter into the frame. Keep
  `negative_prompt` for FAL/Flux, but for every unsupported provider record it
  in `CallResult.unsupported` and leave `prompt` untouched.
- Expect deterministic output paths to overwrite an earlier run.
- Use only HTTP(S) URLs with `--image-url`.
- Expect a brief with no `sections` to render a title-only poster in any
  family; the layout only asks for zones the brief has copy for.

## Verification

- Confirm `lith-generate --help` and `lith-run --help` exit 0.
- Confirm `python -c "from lith import render_prompt"` exits 0 in environments
  that install lith as a library dependency.
- Confirm `lith-run` exited 0. A published file is not the success signal —
  `lith-run` publishes the bytes even when it rejects the frame, so a file
  exists either way.
- Confirm every line of the brief's spec appears in the image, spelled
  correctly, and that no wording from the prompt's own instructions was
  lettered into the frame.
