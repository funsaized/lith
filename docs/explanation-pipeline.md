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

Of those, **lith implements 2, 3, and only the export half of 5.** There is no
crop and no grade — the published file is the model's bytes, unmodified, under
a derived name. Stage 1 is a JSON file you write by hand (or `expand_brief`,
which shells out to an LLM CLI you supply). Stage 4 is a human looking at the
candidates. Stage 6 is a human and a separate tool.

Stage 3 is the one that moved. It used to be a call lith described and left to
somebody else; `lith-press` now makes it.

That is not an unfinished pipeline; it is where the deterministic/probabilistic
line was drawn. Everything on lith's side of the line is pure, testable, and
reproducible: given the same recipe, `render_prompt` returns the same prompt —
copy block and layout description included — forever, and `lith-print` publishes
the model's bytes unchanged under a name derived from that same recipe.
Everything on the other side needs judgment, and lith declines to pretend
otherwise.

The concrete consequence: `lith-print` with no `--image-url` and no `--image-file`
prints its plan and exits 0. The dry run is the default, not a flag, because
the step it can't do — deciding which candidate is the good one — comes at the
end rather than the middle.

## Why the driver now makes the call

For most of this project's life `lith-plate --press --emit-json` emitted an
envelope and stopped. Somebody else made the call and handed the result back.
The argument was that model choice belonged to whoever held the API key, and
that a library with no network is easier to trust.

The argument did not survive contact with a real bridge.

Two full sweeps of the 34-recipe testbed were run through a generation tool that
accepted `prompt` and silently discarded `model`, `n`, `negative_prompt`, and
the exact `aspect_ratio`. Every image came back. Every frame was wrong. The
model that served them was not the one any recipe named, and nothing in the
returned bytes said so. **An envelope is a request, and a request nobody
verifies is a wish.**

So `lith-press` closes the loop. It takes the same envelope, sends it to xAI,
OpenAI, or MiniMax over the standard library, and returns a `CallResult` that
records what actually happened: `model_reported`, `aspect_reported`,
`revised_prompt`, the raw provider payload, and — the field the whole design
turns on — `unsupported`, naming every envelope field the provider could not
accept and why.

Two of the original three reasons survived intact, and shaped how it was built.

**Still no vendor SDK, still no dependency.** `lith.call` is `urllib` and
`json`. The package has zero runtime dependencies and the pure modules —
`render`, `aspect`, `layout`, `recipe`, `styles`, `paths` — still import neither
`lith.call` nor `lith.cli`. A test enforces that, so the prompt side stays
network-free by construction rather than by habit.

**Candidate selection is still a human judgment.** `lith-press` writes every
candidate to disk and ranks none of them. Scoring is stage 4 and no code here
attempts it.

The third reason — that model choice was not lith's to make — was the one that
was wrong. Lith was already the only component that knew which ratios a model
could produce; refusing to also make the call meant that knowledge was applied
to a request nobody honored.

### The rule that came out of it

A field a provider cannot accept is **reported, never smuggled**. No adapter
appends or prepends anything to `prompt`.

`negative_prompt` is the standing example. No provider in this matrix accepts
one — not xAI, not OpenAI, not MiniMax — yet lith still emits it, because
FAL/Flux backends do. The tempting shortcut is to paste it into the positive
prompt. That reverses the instruction, asking the model *for* what the field
was written to forbid, and hands it several hundred more characters it may
letter into the frame. So it goes in `unsupported` and the prompt is sent
byte-for-byte as rendered.

The same rule is why `prompt_optimizer` is sent to MiniMax as an explicit
`False` rather than left to its default. It rewrites the submitted prompt, and
the submitted prompt contains the literal copy block.

## Model routing

There are now two routing decisions, and they answer different questions.

**Which provider?** `call.capability.provider_for_model` maps every model id to
one adapter. An unknown id raises rather than guessing, and the models it knows
are exactly the models `aspect.MODEL_ASPECTS` holds capabilities for — the two
tables are meant to be read together.

**Which road — Hermes or direct?** `lith-press --check` answers this without
calling anything. It uses Hermes' own generation tool only when *both* the
configured model matches the recipe's and the resolved aspect is one of the
three shapes that tool can deliver. Either condition failing routes to
`lith-press`, and the printed `reason` says which one.

The second condition matters as much as the first. Hermes' `image_generate`
takes `landscape`, `square`, or `portrait` — three buckets. A matching model
still returns the wrong frame for `2:3`, `3:2`, or `20:9`, and that translation
is where every frame drift in both sweeps originated.

Underneath both sits `MODEL_ASPECTS`, which exists because an image model does
not reject a ratio it lacks. It substitutes one silently, and the layout in the
prompt was composed for the frame that was requested. Lith would rather
substitute first and say so.

That table is no longer a set of ratios. Three providers need three shapes: a
ratio enum for xAI and MiniMax, a fixed list of pixel sizes for the OpenAI 1.x
line, and a genuinely continuous range for `gpt-image-2`, which accepts any
`WIDTHxHEIGHT` whose edges divide by 16 and whose ratio falls between `1:3` and
`3:1`. A set could express the first and lie about the other two — it once
clamped `20:9` on `gpt-image-2` to a nearby listed value for no reason at all.

### What the table still cannot tell you

`MODEL_ASPECTS` is about frames. It says nothing about whether a model can
letter forty lines of authored copy correctly, and the two properties are
independent. `gpt-image-1` and `gpt-image-1-mini` deliver exact frames and then
drop whole sections, desync headings from the bodies beneath them, and duplicate
panels. `lith-print --strict` exits 0 on every one of those images, because no
exit code inspects copy.

That is recorded in [README → Not every listed model can render a dense
spec](../README.md#not-every-listed-model-can-render-a-dense-spec) rather than
in the capability record, because it is a judgment from a sample rather than a
documented provider limit. It is the kind of thing a table should not pretend
to know.

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

Lith takes input from several places and treats each differently.

**Recipe files are authored input, but their shape is validated.** `load_recipe`
requires a known style and model, a provider-valid candidate count, non-empty
authored strings, well-shaped sections, known layout keys, and a syntactically
positive aspect ratio when one is supplied. `aspect` is deliberately not
required: it has a resolution chain, and demanding it in every recipe would
make most of that chain unreachable. Model-produced briefs pass through the
same `validate_brief` / `recipe_from_brief` boundary before rendering.

**Model-generated image URLs are not.** `--image-url` reaches out to a host
lith didn't choose, so `download()` enforces four guards: HTTP(S) schemes only,
re-checked after redirects; a 30-second timeout; a 25 MB ceiling enforced while
streaming rather than after; and structural JPEG, PNG, or WebP validation before
anything is written to disk. A model API that returns an HTML error page or a
truncated image fails instead of becoming a corrupt published artifact.

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

**Nor is whoever else makes the call.** Clamping only binds a caller that
honors the envelope. A generation tool can accept `aspect_ratio`, `model` and
`negative_prompt`, quietly drop all three, and still return an image — the run
looks clean while the envelope was discarded. That is the failure `lith-press`
was built to end: it sends the fields itself and reports back what the provider
said it did, so `model_reported` and `unsupported` replace an assumption with
evidence. Hand the envelope to something else and you are back to trusting it,
which is why `lith-print --strict` still checks the delivered frame independently
of who produced it.

**Credentials in `~/.hermes/auth.json` are not trusted by name.** Tier 4 of the
credential chain reads a file lith does not own, so a pool entry is used only
when its `auth_type` is `oauth` — the `api_key` entries store a fingerprint, not
a secret — and only when its `base_url` matches that provider's image API.
Matching on the provider name alone would sign an `api.openai.com` request with
a token issued for `chatgpt.com/backend-api/codex`, and fail in a way that looks
exactly like a bad key. Lith reads that file and never writes it.

`--image-file` skips the network guards but keeps structural image validation,
since a local path is your own. Either way the bytes land on a `.part` file first and
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
