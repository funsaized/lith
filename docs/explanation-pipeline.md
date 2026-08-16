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
5. POST-PROCESS    crop, grade, export
6. REVIEW/UPLOAD   human approve → media upload → post
```

Of those, **lith implements 2, and only the export half of 5.** There is no
crop and no grade — the published file is the model's bytes, unmodified, under
a derived name. Stage 1 is a JSON file you write by hand (or `expand_brief`,
which shells out to an LLM CLI you supply). Stage 3 is a call lith emits an
envelope for but never makes. Stage 4 is a human looking at four candidates.
Stage 6 is a human and a separate tool.

That is not an unfinished pipeline; it is where the deterministic/probabilistic
line was drawn. Everything on lith's side of the line is pure, testable, and
reproducible: given the same recipe, `render_prompt` returns the same prompt —
copy block and layout description included — forever, and `lith-run` publishes
the model's bytes unchanged under a name derived from that same recipe.
Everything on the other side needs judgment or a network call, and lith
declines to pretend otherwise.

The concrete consequence: `lith-run` with no `--image-url` and no `--image-file`
prints its plan and exits 0. The dry run is the default, not a flag, because
the step it can't do comes in the middle.

## Why the driver never calls a model

`lith-generate --call --emit-json` emits an envelope — prompt, negative prompt,
aspect ratio, model, n, seed, output path, style, aspect note — and stops. Someone else makes
the call and hands the result back via `--image-url` or `--image-file`.

`negative_prompt` stays in that envelope because FAL/Flux backends accept it.
For a provider that does not, the provider adapter must leave the request's
`prompt` byte-for-byte unchanged and record the rejected field and reason in
`CallResult.unsupported`. It must never append or prepend a negative prompt (or
any other unsupported field) to `prompt`: doing so reverses the negative
instruction and gives the model more text it may letter into the image.

Three reasons this split is worth the extra hop:

**No credentials, no vendor SDK, no network in the library.** Lith has zero
runtime dependencies beyond the standard library and no external binaries. It
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

Nothing in the code routes between models. `--model` records a choice that
somebody else acts on, and the only model knowledge lith holds is
`aspect.MODEL_ASPECTS` — which ratios each one can actually produce.

That table exists because an image model does not reject a ratio it lacks. It
substitutes one silently, and the layout in the prompt was composed for the
frame that was requested. Lith would rather substitute first and say so.

The current generation is `grok-imagine-image-2.0` and `gpt-image-2`, and the
default is grok. Both are far more capable than what they replace, in a way that
closed a real wound: `gpt-image-1` offered exactly three ratios, so four of the
seven families — everything defaulting to `16:9` — were clamped to `3:2` the
moment you pointed them at OpenAI. `gpt-image-2` has `16:9`, and every family
default is now clean on both current models without any family changing.

The older ids remain callable and remain in the table, because a recipe pinning
`gpt-image-1` should still get a warning rather than a silent reframe.

Two gaps worth knowing. `minimax-image` has no entry, so it is never clamped and
never warned about — a deliberate omission rather than an oversight, since an
unknown model should not be second-guessed. And `--model` is an argparse
`choices` list, so the *flag* rejects an unlisted id while a recipe file does
not: `load_recipe` takes `model` at face value. That asymmetry is the seam to
watch when a new model ships.

## Why the copy is specified, never improvised

Image models render text badly. Not always, but often enough that letting one
choose the words means shipping occasional gibberish under your own name.
Asking for "a poster about our Tailscale setup" gets you plausible-looking
labels naming ports you don't use.

So lith splits authorship from rendering. Every word that will appear in the
frame is written down first — by you in the recipe, or by an LLM through
`expand_brief`, whose prompt is explicit that "every word you write is printed
verbatim into the image." `render.format_spec` then serializes that brief into
a literal copy block:

```
TITLE: TAILSCALE
SUBTITLE: A PRIVATE CLOUD IN THREE MACHINES
SECTION 1 HEADING: 01 - THE HUB
    - Mac mini M4, always on
    - mosh survives every dropped link
FOOTER: s11a.com
```

and the family template drops it in under a standing order: *render the copy
below exactly as written, spelled character for character, in the structure
given; do not invent, paraphrase, abbreviate, translate, reorder, or add any
word that is not listed here.* The negative prompt pushes the same way —
`invented words`, `lorem ipsum`, `misspelled words`. The model still draws the
glyphs, but it is never the author. That field is useful only on backends such
as FAL/Flux that expose a negative-prompt parameter. On providers that do not,
it is surfaced in `CallResult.unsupported`, not concatenated into the positive
prompt.

`layout.format_layout` is the other half. It emits only the zones the brief
actually has copy for, arranged by one of
[fifteen named layouts](explanation-layouts.md). An unconditional skeleton would
contradict the verbatim rule directly — told to draw a section grid with no
sections to put in it, the model fills the boxes with invented copy.

The two blocks are kept rigidly apart, and the boundary is the whole design.
Everything in the copy block is lettered; nothing else is. That is why a
`diagram` lives in the layout block rather than the copy block — it is a
description of a picture, not a quotation — and why zone notes are lowercase
prose. When they were ALL-CAPS labels, three of seven families lettered
`TITLE BLOCK` and `4 SECTION PANELS` into real output as visible headings.

**This narrows the failure mode; it does not close it.** A model can still
misspell a word it was handed. What it can no longer do is decide what the
words are, which is the difference between a typo you catch on review and a
confident false claim you don't. Reviewing candidates means reading every
character against the spec, which is why stage 4 stays a human.

## Trust boundaries

Lith takes input from three places and treats them differently.

**Recipe files are trusted.** You wrote them. `load_recipe` validates that the
brief carries `topic`, `headline` and `icon`, and otherwise takes the JSON at
face value. `aspect` is deliberately not required: it has a resolution chain,
and demanding it in every recipe would make most of that chain unreachable.

**Model-generated image URLs are not.** `--image-url` reaches out to a host
lith didn't choose, so `download()` enforces four guards: HTTP(S) schemes only,
re-checked after redirects; a 30-second timeout; a 25 MB ceiling enforced while
streaming rather than after; and a magic-byte check for JPEG, PNG, or WebP
before anything is written to disk. A model API that returns an HTML error page
fails at the magic-byte check instead of becoming a corrupt `.jpg`.

**Spec copy is trusted but shape-checked.** The strings in `sections` and
`footer` are yours, and `format_spec` passes them through unescaped — they are
going into a prompt, not a shell. What it checks is shape: a section without a
`heading` raises `ValueError` naming its index, and an unknown `layout` or
`diagram_position` raises with the valid options listed, rather than silently
falling back to a default the recipe did not ask for.

**Model capabilities are not trusted either.** A model asked for a ratio it
cannot produce substitutes one silently. Lith clamps the request to the model's
real capability set before the call, and compares the published image's actual
dimensions against the request afterward — the layout in the prompt was composed
for the frame that was asked for.

**Nor is the tool that makes the call.** Clamping only binds whoever honors the
envelope. A generation tool that accepts `aspect_ratio`, `model` and
`negative_prompt` and then quietly drops them still returns an image, so the
run looks clean while the envelope was discarded. Of the five fields, the frame
is the only one lith can check from the returned bytes, which is why `--strict`
exists: it turns that one check into an exit code a batch cannot scroll past.
The other four are unverifiable downstream and have to be confirmed against the
tool's own documentation.

`--image-file` skips the network guards but keeps the magic-byte check, since a
local path is your own. Either way the bytes land on a `.part` file first and
are renamed only once the format is known — not for crash safety but because
the extension is a property of the bytes, and lith refuses to guess it from the
recipe. Both paths buffer the whole body and write it once, after their guards
pass, so a rejected image never reaches the disk at all.

## Deliberate omissions

**Video is out of scope.** Image-to-video models warp small text under any
motion prompt — precisely the section panels the spec exists to get right, and
the one thing a still image gets to hold steady. Adding video means deciding
whether the copy is re-rendered per frame, held as a static plate over the
motion, or drawn afterwards with something like `ffmpeg drawtext`. Each is a
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
- [About output styles](explanation-output-styles.md) — how one spec renders
  seven ways
- [About layouts](explanation-layouts.md) — how panels get arranged
- [About the design language](explanation-design-language.md) — the palette and
  composition rules underneath the seven
- [README → Status](../README.md#status) — the per-component build state
