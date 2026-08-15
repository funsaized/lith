# About the pipeline

Lith is smaller than it looks. This page explains what the code actually does,
which stages are deliberately left to a human or an agent, and why the
boundaries fall where they do.

For the flags and signatures, see [README → CLI reference](../README.md#cli-reference).

---

## What runs, and what doesn't

The intended shape of the full pipeline is six stages:

```
1. INGEST          topic brief + copy + style pick + aspect
2. STYLE BIBLE     pull the family template, substitute the brief
3. GENERATE        N candidates from an image model
4. SCORE           brand-DNA + readability + concept fit
5. POST-PROCESS    typography overlay, crop, grade, export
6. REVIEW/UPLOAD   human approve → media upload → post
```

Of those, **lith implements 2 and the typography half of 5.** Stage 1 is a
JSON file you write by hand (or `expand_brief`, which shells out to an LLM CLI
you supply). Stage 3 is a call lith emits an envelope for but never makes.
Stage 4 is a human looking at four candidates. Stage 6 is a human and a
separate tool.

That is not an unfinished pipeline; it is where the deterministic/probabilistic
line was drawn. Everything on lith's side of the line is pure, testable, and
reproducible: given the same recipe, `render_prompt` returns the same prompt
forever, and given the same image and lines, `overlay_typography` writes the
same pixels. Everything on the other side needs judgment or a network call, and
lith declines to pretend otherwise.

The concrete consequence: `lith-run` with no `--image-url` and no `--image-file`
prints its plan and exits 0. The dry run is the default, not a flag, because
the step it can't do comes in the middle.

## Why the driver never calls a model

`lith-generate --call --emit-json` emits an envelope — prompt, negative prompt,
aspect ratio, model, n, seed, output path, style — and stops. Someone else makes
the call and hands the result back via `--image-url` or `--image-file`.

Three reasons this split is worth the extra hop:

**No credentials, no vendor SDK, no network in the library.** Lith has zero
runtime dependencies beyond the standard library and an ImageMagick binary. It
installs and runs anywhere Python 3.10 does, and the test suite needs no
mocking of an HTTP client that isn't there.

**Model choice is not lith's to make.** The `--model` choices exist to be
recorded in the envelope, not dispatched on. Whoever holds the API key picks
the provider, and swapping providers changes nothing in this repository.

**Candidate selection is a human judgment.** Four candidates come back and one
is right; scoring that is stage 4, and no code here attempts it. An envelope
that a person or an agent consumes keeps the decision where the taste is.

The practical cost is that the operator — or a Hermes session driving the CLI —
has to bridge two commands. That's the trade.

## Model routing

Nothing in the code routes between models; the `--model` flag records a choice.
The routing that has worked in practice:

| Model family | Share | Why |
|---|---|---|
| **Grok** (`grok-imagine-image-quality`, `grok-imagine-image`) | ~70% | Best at committed, unusual aesthetics — manga tape-insert, woodcut, neon brutalist. Supports image-to-image, so a style reference can be locked and re-rendered. |
| **OpenAI** (`gpt-image-1`) | ~20% | Better at coherent typography inside the frame. Use for family E and anywhere in-image text is non-negotiable. |
| **MiniMax** (`minimax-image`) | ~10% | Cheap variation, background patterns, vector-flat stickers, throwaway rounds. |

Grok first, OpenAI second, MiniMax third — and always at least four candidates
per call, which is why `n` defaults to 4 in both the CLI and `load_recipe`. The
hit rate on a first candidate is far lower than most people expect.

## Why typography is a separate pass

Image models render text badly. Not always, but often enough that shipping
model-drawn body copy means shipping occasional gibberish under your own name.
Small monospaced text is the worst case: at 25pt the letterforms smear, and
near-misses on product names look like typos rather than artifacts.

So lith splits the frame in two. The model owns visual layout — composition,
palette, illustration, the giant headline where a wrong glyph would be obvious
enough to catch. `overlay_text.py` owns every literal character that must be
correct, drawn with ImageMagick in a real font at a fixed position:

```
magick input.jpg
  -fill #000000 -draw "rectangle 120,365 1165,515"   # mask the model's attempt
  -font Menlo.ttc -pointsize 25
  -fill #FF3030 -annotate +150+405 "[SYSTEM]"        # label
  -fill #00E5FF -annotate +295+405 "32 language..."  # body
  output.png
```

The mask is the important part: the overlay paints a black rectangle over the
region first, then draws on top. Whatever the model invented in that band is
gone before our copy lands.

This is also why `overlay_typography` shells out to `overlay_text.py` rather
than building the `magick` argv inline. The script owns a set of
dimension-specific tuning constants — mask rectangle, baseline, line height,
the two column x-offsets — and two copies of those constants would drift.

**The constants are tuned for one layout.** The defaults assume a 1280×720
family-B panel; the mask `120,365 1165,515` is a band in that specific frame.
On a 4:5 patent diagram they land in the wrong place. Overriding them means
calling `overlay_text.py` directly, because `overlay_typography` forwards only
`--font`. Aspect-aware masks are the obvious next piece of work and are not
built.

## Trust boundaries

Lith takes input from three places and treats them differently.

**Recipe files are trusted.** You wrote them. `load_recipe` validates that the
brief carries `topic`, `headline`, `icon`, and `aspect`, and otherwise takes the
JSON at face value.

**Model-generated image URLs are not.** `--image-url` reaches out to a host
lith didn't choose, so `download()` enforces four guards: HTTP(S) schemes only,
re-checked after redirects; a 30-second timeout; a 25 MB ceiling enforced while
streaming rather than after; and a magic-byte check for JPEG, PNG, or WebP
before anything is written to disk. A model API that returns an HTML error page
fails at the magic-byte check instead of becoming a corrupt `.jpg`.

**Overlay copy is trusted but shape-checked.** `--line LABEL=copy` requires both
halves to be non-empty; the values go straight into the `magick` argv as
separate list elements, never through a shell.

`--image-file` skips the network guards but keeps the magic-byte check, since a
local path is your own.

## Deliberate omissions

**Video is out of scope.** Image-to-video models warp small monospaced glyphs
under any motion prompt — precisely the `[SYSTEM]`/`[NEW]`/`[READY]` band at
25pt Menlo that the overlay exists to protect. Adding video means choosing
between overlaying after the video pass, replacing the Menlo+magick path with
`ffmpeg drawtext`, or compositing the still overlay over every frame. Each is a
separate design decision, and none of them is "add a flag."

**Post → brief ingestion is a different project.** This pipeline writes outward:
model APIs it names, filesystem paths it derives. Ingesting a URL or a scraped
post reads inward from untrusted content — a different trust boundary, a
different error budget, and a different invariant (the source post rather than
the literal copy). HTML/OG scraping, a relevance check, and a "riff on this"
prompt deserve their own repository.

**Candidate scoring is not automated.** CLIP-based ranking against the brand-DNA
checklist is plausible and unbuilt. Four candidates and a human eye is the
current stage 4.

**There is no calendar or rotation tool.** The weekly rotation in
[About the design language](explanation-design-language.md#rotating-families) is
a habit, not a scheduler.

## See also

- [Tutorial: your first announcement image](tutorial-first-image.md) — every
  stage above, run once, end to end
- [About the design language](explanation-design-language.md) — why the seven
  families exist and what they share
- [README → Status](../README.md#status) — the per-component build state
