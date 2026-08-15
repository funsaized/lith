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
the brief doesn't provide, instead of substituting something plausible. A
silently dropped slot is a silently drifted style.

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
- **One subject, one idea.** Every image is a single declarative statement, not
  an eight-bullet infographic. Two ideas means two images.
- **Posters, not slides.** Readable from a thumbnail, designed to be re-pinned.
- **Hand-drawn energy.** Even the most polished family carries an asymmetric
  composition, an off-center alignment, or one decorative flourish.
- **A shared iconography.** Lightning bolts, sparkles, skulls, magnifying
  glasses, telescopes, gears, concentric circles, and framing devices like
  "1Q", "Chapter", "Issue 001", mock newspaper mastheads. Each family declares
  its own allowed set in its `iconography` array.

Those last constraints appear in `styles.json` under `rules` — not because
anything enforces them at runtime, but because they are the checklist a human
scores candidates against.

## The seven families

Each family below names the aesthetic, what it's for, and the trap it avoids.
The literal prompt text lives in `styles.json`; it is not reproduced here,
because a second copy of a prompt template is a copy that goes stale.

**A — Sticker / whisper-joke infographic.** Multi-panel sticker sheet on near-
black, neon flat shapes, oversized text, comic-book bursts. Loud and memetic.
Best for quick reactions and low-stakes "we shipped a thing" posts. Its accent
slot is the only one in the set that carries four candidate colors at once —
`_palette_value` joins them with ` | ` and lets the model pick, because a
sticker sheet wants variety within the frame.

**B — Sci-fi brutalist UI.** A single black panel, a 180px monospaced headline,
a 1px cyan grid, one silhouette at 20% opacity. Mission control. Best for
feature flagships and capability reveals, and the most reliably legible of the
seven at thumbnail size. This is the family the bundled recipe and the overlay
defaults are tuned for.

**C — Vintage technical manual / patent diagram.** Sepia paper, fine ink lines,
double-rule border, patent-style "FIG. 1" callouts. Best for "how it works"
posts, where the aesthetic itself makes the claim that something was
engineered. The only family that uses the `{volume}` slot.

**D — Manga tape-insert / risograph.** One bold flat ground, thick manga
outlines, screen-tone shading, registration offset. Best for release
announcements and "chapter" framing. The only family where panels are the
point — the one-idea-per-image rule bends here and nowhere else.

**E — Editorial screenshot polish.** A real product screenshot on a deep purple
gradient with a radial glow. Best for UI demos. It is also the family that
comes closest to the generic-AI-gradient failure mode, which is the price of
using a gradient at all; it survives because the screenshot is real content,
not a rendered abstraction.

**F — Woodcut / analog engraving.** Black on cream, 19th-century cross-hatching,
heavy serif, drop cap. Best for sponsor announcements and "memo from the team"
posts — anywhere gravitas beats energy.

**G — Role-log / status dashboard.** A dark terminal panel of monospaced log
lines with one highlighted success event. Best for operational posts and
build-in-public stats. Nearly monochrome by design: a single accent marks the
moment that matters.

You can also produce multi-family strips — three or four panels, each in a
different family — for a monthly signature post. Nothing in the code assembles
these; it's a manual composite of separate runs.

## Prompt anatomy

Every family template covers the same six slots, in this order:

```
[FRAME]      aspect, composition, camera/vantage, foreground/background
[PALETTE]    2-4 colors with hex codes; one accent per image
[TYPO]       font + size + weight + color, headline vs body distinction
[ICON]       one or two named motifs/glyphs (lightning, skull, gear)
[COPY]       any literal text that must appear in the image (use sparingly)
[MOOD]       one sentence: who is this for, what is the feeling
```

They're prose in `prompt_template` rather than labeled sections, but the order
holds across all seven, and a new family should follow it. The rules behind the
order:

1. **Never let the model choose a font.** Say "display sans-serif, Helvetica
   Neue Black, 180px" or "Bodoni, 200px, all caps." An unspecified font is a
   different font every run.
2. **In-image text should be one to three words.** "The Crew." "New in Hermes."
   "1Q." "Just /run." Anything longer is a caption, and captions belong in the
   post, not the picture. `rules.max_words_in_image` records this as 3.
3. **Hex codes beat color names.** "Hot magenta" varies run to run; `#FF2E88`
   does not.
4. **One decorative flourish per image.** A lightning bolt, a spark, a
   sunburst, a single ornamental rule. Five decorations read as clutter; one
   reads as a signature.
5. **Asymmetry wins.** Centered-everything reads as a stock template. Offset
   the headline, place the icon opposite, connect them with a flourish.
6. **One image, one idea** — except family D.

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
product names, and letterforms that fall apart at small sizes. This is the
entire reason `overlay_typography` exists — see
[About the pipeline](explanation-pipeline.md#why-typography-is-a-separate-pass).

**The AI-gradient trap.** Purple-to-blue diagonal gradient, 3D-rendered icon,
gloss highlight. If the result has all three, generation drifted to the
training-set average. Reject and re-prompt rather than accepting it; each
family's `negative_prompt` exists to push against this, but negatives are a
nudge, not a guarantee.

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
- [README → Style families](../README.md#style-families) — the field reference
