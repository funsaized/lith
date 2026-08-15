---
name: tech-image-pipeline
description: Generate brand-consistent tech and AI social images with the funsaized tech-image-pipeline by rendering briefs through seven style families, coordinating image generation, and overlaying literal copy with ImageMagick. Use when a user asks for an image for a post, announcement, or feature; references style families A-G or the Teknium aesthetic; or wants a topic expanded into a complete image brief.
---

# Tech-Image Pipeline

Use Python for deterministic prompt, path, recipe, and typography work. Use the
active model session for topic expansion and image generation.

## Architecture

- Read `templates/styles.json` for the seven family recipes.
- Use `scripts/pipeline/` for rendering, recipes, paths, styles, typography, and expansion.
- Use `scripts/generate.py` to render a prompt and emit a model-call envelope.
- Use `scripts/run.py` to ingest a remote or local generated image and write the final artifact.
- Treat `scripts/overlay_text.py` as the single source of truth for ImageMagick arguments. Do not duplicate its constants in `pipeline/typography.py`.
- Save repeatable briefs in `recipes/*.json`.

## Workflow

1. Read `templates/styles.json` and select the family that fits the topic.
2. If the user supplied only a topic, use `expand_brief()` or expand the required brief fields: `topic`, `headline`, `icon`, and `aspect`.
3. Save or select a recipe, then render its model-call envelope:

   ```bash
   PYTHONPATH=. python scripts/generate.py \
     --recipe recipes/<name>.json --call --emit-json
   ```

4. Call the available image-generation tool with the envelope's `prompt`, `negative_prompt`, `aspect_ratio`, `model`, and `n`. Ask the user to choose when multiple candidates need subjective selection.
5. Pass the chosen image URL to the driver and provide literal overlay lines:

   ```bash
   PYTHONPATH=. python scripts/run.py --recipe recipes/<name>.json \
     --image-url <url> \
     --line SYSTEM='...' --line NEW='...' --line READY='...'
   ```

6. For local debugging or smoke tests, use `--image-file <path>` instead of `--image-url`.

## Conventions

- Keep headlines to 1-3 all-caps, ASCII-friendly words.
- Default feature posts to `16:9`, mobile posts to `4:5`, and square posts to `1:1`.
- Overlay literal copy with `overlay_typography`; let the image model handle visual layout, not exact body copy.
- Keep the output scope to content creation. Do not publish, post, or upload unless the user separately asks and authorizes it.

## Verification

- Confirm `outputs/<family>_<headline>.png` exists and is non-empty.
- Visually verify that overlay lines are readable: red label, cyan body, monospace.
- Verify that the family template's headline appears at its intended scale.

## Pitfalls

- Treat image-generation URLs as remote inputs for `--image-url`; use `--image-file` for local paths. The URL path rejects `file:`, `data:`, and other non-HTTP(S) schemes.
- Prefer `B_brutalist` when no family is requested; it has the strongest end-to-end coverage.
- Remember that overlay masks are tuned for 1280x720 family B images. Other aspects can show boundary artifacts.
- Treat recipe `n` as the requested candidate count. Select one candidate manually; the pipeline consumes only one image.
- Copy old artifacts elsewhere before rerunning a recipe when they must be preserved. Output paths are deterministic and later runs overwrite them.
