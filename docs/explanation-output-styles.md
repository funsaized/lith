# About output styles

Seven families, one spec. The same recipe — same title, same panels, same body
lines — renders as a mission-control readout, an Edwardian patent drawing, a
sticker sheet, or a deploy log, and the words come out identical in every one.
This page is about how that separation works and how to choose between them.

For the family table, see [README → Style families](../README.md#style-families).
For why the families exist at all, see
[About the design language](explanation-design-language.md).

---

## One grammar, seven accents

Every family template answers the same four questions, in the same order, about
the same zones:

- how the **title** is set
- what a **section panel** is made of
- how the **drawing** is rendered
- what the **footer** sits on

The zones themselves come from
[`format_layout`](reference-python-api.md#format_layout) and are identical
across all seven. What differs is only the answer to "what is a panel made of":

| Family | A section panel is… |
|---|---|
| **A** Sticker | A rounded-rectangle sticker in one accent colour, heading reversed out of a solid top strip |
| **B** Brutalist | A HUD block outlined 1px cyan, heading in a solid cyan bar, body lines led by red markers |
| **C** Patent | A thin double-ruled box, small-caps serif heading over a hairline, body as numbered callouts |
| **D** Manga | A hand-drawn box with the heading in a bold inverted banner strip |
| **E** Screenshot | A rounded card with a 1px white border at 10% opacity on the gradient |
| **F** Woodcut | Bounded by thin black rules, small-caps serif heading over a hairline, drop cap on the first line |
| **G** Log | A rounded terminal card in `#06141F`, muted header row, body as log entries with green status glyphs |

This is why the copy path is worth defending so hard. A brief is portable: the
same words survive a change of family untouched, because the family never had
any say over them. Changing `"style": "B"` to `"style": "F"` re-skins a poster
without re-authoring it.

## Choosing one

The families are not interchangeable, and the choice is mostly about what the
aesthetic *claims*:

**B — Sci-fi brutalist.** The most reliably legible of the seven at thumbnail
size: pure black, monospace, hard rectangles, no ornament competing with text.
When the content matters more than the styling, this is the safe pick.

**C — Vintage technical manual.** The aesthetic itself makes the argument that
something was engineered. In testing it renders structure more faithfully than
any other family — it landed a clean 2×2 with leader-lined figure callouts on
the first attempt. Best for how-it-works explanations.

**G — Role-log.** Reads as machine output rather than marketing, which is
exactly right for operational posts and build-in-public stats, and exactly wrong
for a launch.

**A — Sticker.** Loud, memetic, near-black with neon accents. Quick reactions
and low-stakes ship announcements. The density of decoration works against dense
copy, so keep the panel count low.

**D — Manga risograph.** Chunky display type on a flat colour ground with
registration offset. Release announcements and chapter framing — the family that
looks like a T-shirt.

**E — Editorial screenshot.** The only family built around real product imagery,
and the one closest to the generic-AI-gradient failure mode. It survives because
a real screenshot is real content rather than a rendered abstraction.

**F — Woodcut.** Gravitas. Sponsor announcements, team memos, anything that
wants to read as a broadside rather than a post.

## Where the families fight the content

Two conflicts are worth knowing because both produced real defects.

**Typography can contradict the copy.** F specified a Garamond-class serif,
which brings old-style figures — numerals that drop below the baseline. `1`
renders as a form that reads as `I`, so `s11a.com` came out as `sIIa.com` and
`DNS-01` as `DNS-0I`. The characters were technically correct and the *word* was
wrong. F now demands lining figures explicitly and names the failure it is
avoiding, because "use lining figures" alone was an instruction the model could
nod at without acting on.

The general lesson: a family choosing a typeface is choosing how digits, ligatures
and small caps behave, and those choices can silently corrupt copy the verbatim
rule was supposed to protect. The copy block guarantees which *characters* are
requested, not which glyphs a face will use to draw them.

**Decoration competes with text.** Every family names its ornament — lightning
bolts, sparkles, fleurons, screen tone — and every family is told to keep them
in empty corners, never over text. That instruction is load-bearing rather than
polite. The families with the most decoration (A, D) are the ones where dense
copy is hardest to keep legible, which is a real reason to prefer fewer sections
in those families rather than a reason to fix them.

## Negative prompts do a specific job

Each family carries a `negative_prompt`, and roughly half of every one of them
is now about text failure: `lorem ipsum`, `garbled text`, `misspelled words`,
`invented words`, `illegible text`, `duplicated letters`,
`text overlapping artwork`. F adds `old-style figures` and
`digits rendered as letters`.

The other half is about aesthetic drift — pushing away from the
purple-gradient-and-3D-icon average that every image model regresses toward when
underspecified. Negatives are a nudge rather than a guarantee, which is why the
positive template is long and specific: the reliable way to not get a gradient
is to describe something else in detail.

**And on the current providers, that nudge never arrives.** Neither xAI, OpenAI,
nor MiniMax accepts a negative prompt on its image endpoint. Every family still
carries one, because FAL/Flux backends do accept them and the field costs
nothing to keep — but for the three providers `lith-press` reaches, the field is
reported in `CallResult.unsupported` and never sent.

That is worth knowing when reading a family's `negative_prompt` as though it
were doing work. It explains why the positive template carries so much weight:
the long, specific description was never a belt-and-braces companion to the
negatives. On these providers it is the only thing holding the aesthetic, and
the only thing standing between a dense spec and garbled copy.

Whether a negative prompt would have helped is a question this project cannot
answer from its own output, since it has never delivered one.

## The frame a family asks for

Four families default to `16:9` and three to `2:3`, and until recently that was
a promise lith could not keep on every endpoint. `gpt-image-1` produces three
sizes total, so a landscape family pointed at it comes back reframed — that
model still clamps `16:9` to `3:2`, and says so.

The current generation removed the constraint rather than widening it.
`grok-imagine-image-2.0` accepts fourteen named ratios; `gpt-image-2` accepts
*any* `WIDTHxHEIGHT` whose edges divide by 16 and whose ratio sits between `1:3`
and `3:1`. Every family default falls comfortably inside both, and so does every
ratio a brief is likely to ask for — a `20:9` banner renders as `20:9`, not as
the nearest thing a list happened to contain.

The lesson generalises past this particular fix: a family's `default_aspect` is
a claim about the frame its composition needs, and that claim is only as good as
the model's willingness to honour it. Lith checks it twice — clamping before the
call, and comparing the published image's real dimensions after — because a
reframed poster is a layout rendered into a frame it was not composed for.

Which model renders a family is a separate question from which frame it can
produce, and the two do not track together. Two OpenAI models deliver exact
frames and then lose whole sections of copy; see
[README → Not every listed model can render a dense
spec](../README.md#not-every-listed-model-can-render-a-dense-spec). A family is
a claim about composition, not a guarantee that any given model can letter it.

## What all seven share

Beneath the differences, the constants are deliberate: dark grounds dominate
(the two paper families are the exceptions, where a dark ground would fight the
metaphor), at most three accent colours, oversized titles, and one decorative
motif rather than five.

Those live in `styles.json` under `rules`, and no code reads them — they are the
checklist a human scores candidates against. They also now carry an asterisk.
`max_words_in_image: 3` and `always_one_idea_per_image` describe the system
before it was spec-driven; a dense poster is a hundred-odd words and several
ideas on purpose. The rules that still hold universally are the palette and
composition ones.

## See also

- [About layouts](explanation-layouts.md) — the arrangement each family renders
- [About the design language](explanation-design-language.md) — the palette,
  typography and composition rules underneath all seven
- [README → Style families](../README.md#style-families) — the field reference
