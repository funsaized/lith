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
recipe loading, output paths, and typography. Use the active session for image
generation and optional topic expansion.

## When to use

- Generate an image for a post, announcement, or feature.
- Work with one of the seven style families A-G.
- Expand a topic into a complete image brief.

## Prerequisites

- Install the CLI tools with
  `uv tool install git+https://github.com/funsaized/lith`.
- Put ImageMagick 7's `magick` command on `$PATH` for typography overlays.
- Add lith to the current Python environment before using the in-process API.

## Workflow

1. Render the recipe and obtain the model-call envelope:

   ```bash
   lith-generate --recipe /absolute/path/to/recipe.json --call --emit-json
   ```

2. Call the available image-generation tool with `prompt`,
   `negative_prompt`, `aspect_ratio`, `model`, and `n`. Ask the user to choose
   when multiple candidates require subjective selection.

3. Pass the chosen HTTP(S) image URL and literal overlay copy to the driver:

   ```bash
   lith-run --recipe /absolute/path/to/recipe.json \
     --image-url <url> \
     --line SYSTEM='...' --line NEW='...' --line READY='...'
   ```

4. Use `--image-file /absolute/path/to/image` instead of `--image-url` for a
   local source.

Use the library directly when lith is installed in the active Python
environment:

```python
from lith import load_recipe, render_prompt, overlay_typography

recipe = load_recipe("/absolute/path/to/recipe.json")
rendered = render_prompt(recipe)
```

## Conventions

- Keep headlines to 1-3 all-caps, ASCII-friendly words.
- Default feature posts to `16:9`, mobile posts to `4:5`, and square posts to
  `1:1`.
- Let the image model handle visual layout; use `overlay_typography` for exact
  literal copy.
- Do not publish, post, or upload unless the user separately authorizes it.

## Pitfalls

- Treat recipe `n` as the requested candidate count and select one candidate
  manually.
- Expect deterministic output paths to overwrite an earlier run.
- Use only HTTP(S) URLs with `--image-url`.
- Expect overlay masks tuned for 1280x720 family B images to show artifacts at
  other aspect ratios.

## Verification

- Confirm `lith-generate --help` and `lith-run --help` exit 0.
- Confirm `python -c "from lith import render_prompt"` exits 0 in environments
  that install lith as a library dependency.
- Confirm the final output exists, is non-empty, and has readable overlay copy.
