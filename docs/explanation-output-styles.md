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
