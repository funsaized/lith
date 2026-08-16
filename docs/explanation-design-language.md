# About the design language

Lith ships seven style families, a fixed palette vocabulary, and a set of
composition rules. This page explains where those came from and why they are
constraints rather than suggestions. For the machine-readable versions, read
[`src/lith/data/styles.json`](../src/lith/data/styles.json); for the field
reference, see [README → Style families](../README.md#style-families).

---

## Why families exist at all

Ask an image model for "a tech announcement graphic" and you get generic SaaS
stock: a purple-to-blue gradient, a 3D-rendered icon, a gloss highlight. The
model averages its training data, and the average tech graphic is forgettable.

The families exist to move the aesthetic decision off the model and onto the
author. Each family is a committed, specific look — a look someone actually
chose. `styles.json` encodes each one as a `prompt_template` with a handful of
slots; the brief fills the slots and nothing else. The model gets no room to
pick a style, because the style arrived pre-decided.

That is why `render_prompt` raises `KeyError` when a template references a slot
lith does not supply, instead of substituting something plausible. A silently
dropped slot is a silently drifted style.

## The brand underneath the seven

The families look nothing alike, and that's deliberate — variety inside a
strict signature is the point. What stays constant across all seven:

- **Dark grounds dominate.** Deep navy `#0A0E1A`, ink black `#000000`,
  midnight teal `#06141F`. Roughly 70% of outputs. The two exceptions
  (C_patent's sepia, F_woodcut's cream) are analog-paper families where a dark
  ground would fight the metaphor.
- **At most three accent colors, from one family.** Hot magenta, cyan, acid
  yellow, rust orange. Never a rainbow. `styles.json` encodes this as
  `rules.max_accent_colors: 3`.
- **Oversized typography.** Headlines run 8–15% of frame height. Body copy is
  monospaced or a chalkboard serif.
- **One subject, one idea — historically.** This held when an image carried
  three words. It no longer describes the system: every family now renders a
  spec, and a dense poster is several ideas and a hundred-odd words on purpose.
  What survives is the discipline underneath it — every one of those words was
  written down first.
- **Posters, not slides.** Readable from a thumbnail, designed to be re-pinned.
- **Hand-drawn energy.** Even the most polished family carries an off-centre
  alignment or one decorative flourish. The `masonry`, `zigzag`, `diagonal` and
  `sidebar` [layouts](explanation-layouts.md) are where this stopped being an
  aspiration and became selectable.
- **A shared iconography.** Lightning bolts, sparkles, skulls, magnifying
  glasses, telescopes, gears, concentric circles, and framing devices like
  "1Q", "Chapter", "Issue 001", mock newspaper mastheads. Each family declares
  its own allowed set in its `iconography` array.

Those constraints appear in `styles.json` under `rules` — not because anything
enforces them at runtime, but because they are the checklist a human scores
candidates against.

Two of them are now historical. `max_words_in_image: 3` and
`always_one_idea_per_image` describe lith before it was spec-driven; all seven
families now carry `{spec}` and `{layout}`, and a poster is scored against its
spec rather than a word count. The palette and composition rules still hold
universally.

## The seven families

Each family commits to one specific look: sticker sheet, mission-control HUD,
patent drawing, manga insert, editorial screenshot, wood engraving, deploy log.
The literal prompt text lives in `styles.json`, and a second copy of a prompt
template is a copy that goes stale, so it is not reproduced anywhere.

What each family is for, how it renders a section panel, and where its aesthetic
fights the copy: [About output styles](explanation-output-styles.md).

You can also produce multi-family strips — three or four panels, each in a
different family — for a monthly signature post. Nothing in the code assembles
these; it's a manual composite of separate runs.

## Prompt anatomy

Every family template covers the same six concerns, in this order:

```
[FRAME]      ground, texture, and the overall visual register
[LAYOUT]     the zone notes, substituted at {layout}
[TYPO]       how the title, panels, drawing and footer are drawn in this family
[ICON]       one or two named motifs/glyphs (lightning, skull, gear)
[COPY]       the literal copy block, substituted at {spec}
[MOOD]       one sentence: who is this for, what is the feeling
```

`[LAYOUT]` and `[COPY]` are shared verbatim across all seven — the same two
substituted blocks, in the same order, with the same standing order to reproduce
the copy character for character. Only `[FRAME]`, `[TYPO]`, `[ICON]` and
`[MOOD]` are the family's own. That ratio is the point: a family decides how a
poster looks, never what it says.

They're prose in `prompt_template` rather than labeled sections, but the order
holds across all seven, and a new family should follow it. The rules behind the
order:

1. **Never let the model choose a font.** Say "display sans-serif, Helvetica
   Neue Black, 180px" or "Bodoni, 200px, all caps." An unspecified font is a
   different font every run.
2. **Every word is authored before it is drawn.** A title-only poster and a
   six-panel explainer travel the same path: the copy block. `rules.max_words_in_image`
   records an older answer of 3; the working limit is now 60–140 words of body
   copy, and the constraint that replaced the word count is that somebody wrote
   each one down first.
3. **Hex codes beat color names.** "Hot magenta" varies run to run; `#FF2E88`
   does not.
4. **One decorative flourish per image.** A lightning bolt, a spark, a
   sunburst, a single ornamental rule. Five decorations read as clutter; one
   reads as a signature.
5. **Asymmetry wins.** Centered-everything reads as a stock template. Offset
   the headline, place the icon opposite, connect them with a flourish.
6. **One image, one argument.** Several panels are fine; several unrelated
   claims are not. Sections should be facets of one thing.

## Rotating families

Using one family repeatedly trains the audience to scroll past. A workable
weekly rotation:

| Day | Family | Why |
|---|---|---|
| Mon | A — Sticker | Loud, memetic, week-start energy |
| Tue | B — Sci-fi brutalist | Engineer flagship |
| Wed | C — Vintage manual | Educational, "how it works" |
| Thu | D — Manga tape-insert | Vibrant, viral-leaning |
| Fri | E — Editorial screenshot | Product UI demo |
| Sat | F — Woodcut | Gravitas, sponsor, "memo" |
| Sun | G — Role-log | Quiet operational post |

This is a habit, not a feature — no calendar tool exists in the codebase. Once
a month, a multi-family mash-up signals deliberate range and tends to be the
highest-engagement pattern of the set.

## Failure modes

The recurring ways output goes wrong, in rough order of how often they bite:

**Model-rendered text is the primary failure mode.** Treat every character the
model draws as suspect. It will produce convincing gibberish, near-misses on
product names, and letterforms that fall apart at small sizes. This is why the
copy is written into the brief and the model is ordered to reproduce it
verbatim rather than invent it — see
[About the pipeline](explanation-pipeline.md#why-the-copy-is-specified-never-improvised).
The order narrows the failure to misspelling, so read every line of a candidate
against the spec before shipping it.

**The AI-gradient trap.** Purple-to-blue diagonal gradient, 3D-rendered icon,
gloss highlight. If the result has all three, generation drifted to the
training-set average. Reject and re-prompt rather than accepting it. Each
family's `negative_prompt` was written to push against this — but none of the
three providers `lith-call` reaches accepts a negative prompt, so on those the
only thing holding the aesthetic is how specifically the positive template
describes something else.

**A typeface can corrupt copy the verbatim rule protected.** Family F specified
a Garamond-class serif, which brings old-style figures — numerals that sit below
the baseline. `s11a.com` rendered as `sIIa.com` and `DNS-01` as `DNS-0I`: the
right characters, the wrong word. The copy block guarantees which characters are
requested, never which glyphs a face draws them with, so a family choosing a
typeface is also choosing how digits and small caps behave.

The fix carried its own lesson. F's template was amended to name the failure —
quoting `s11a.com` and its corrupted form as an example of what not to do — and
on a title-only brief the model lettered the *counter-examples* into the poster.
A warning written as a quotation is still text in the prompt. The instruction now
describes the failure without spelling it, and a test refuses any template
carrying a content-shaped literal.

**Panel area decides legibility, more than anything in the palette.** The same
dense brief that leaked style instructions into its title at a 1k render came
back exact at 2k, on the same model with the same prompt. Nine panels in a
1280×720 frame give each panel roughly a tenth of the pixels it needs; the text
degrades first, and what fills the gap is whatever the model can read nearby.
Before blaming a family for garbling copy, count the panels and check the frame
— a portrait frame, fewer sections, or `--resolution 2k` fixes more than any
prompt edit.

**A near-empty brief invites the template into the frame.** A family whose
composition implies multiplicity cannot render a title-only poster. Asked for a
*sticker sheet* with one line of copy, A builds the sheet anyway and fills five
stickers from the nearest concrete strings in the prompt — palette hex codes and
a font name. F, asked for the same thing, renders a clean broadside, because a
broadside with one headline is a coherent object and a sheet with one sticker is
not. `render_prompt` emits a `copy_note` when the copy block is thin relative to
the instructions around it; it correctly flags both cases and cannot tell you
which way the family will resolve them.

**Instructions can be mistaken for content.** When zone notes were ALL-CAPS
labels, three families lettered `TITLE BLOCK` and `4 SECTION PANELS` into real
images. Anything in the prompt that reads like a heading may be drawn as one —
see [About layouts](explanation-layouts.md#the-instructioncontent-boundary).

**Hands, faces, and real logos are unreliable.** Push toward illustration and
silhouette; never toward photoreal people or a specific vendor's mark.

**Letting the model pick the style.** Covered above, and worth repeating,
because it's the failure that produces work that looks like everyone else's.

**Sameness.** Five posts from the same family and the audience tunes out. The
rotation above is the mitigation.

**Weak captions.** The image carries the aesthetic; the caption carries the
claim. Short, technical, dry, forward-looking. No "excited to announce."

## See also

- [Tutorial: your first announcement image](tutorial-first-image.md) — the
  design language applied end to end
- [About the pipeline](explanation-pipeline.md) — how the stages fit together
  and what's deliberately not built
- [About output styles](explanation-output-styles.md) — what each family is for
- [About layouts](explanation-layouts.md) — how panels get arranged
- [README → Style families](../README.md#style-families) — the field reference
