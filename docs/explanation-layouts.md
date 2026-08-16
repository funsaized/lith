# About layouts

A lith brief carries words, not positions. Somewhere between the recipe and the
image, something has to decide that four panels sit in a 2×2 grid rather than a
column, and that the drawing goes underneath rather than in the middle. This
page is about that decision: what the vocabulary is, who chooses, and why the
choosing is split the way it is.

For the keys themselves, see [README → Layouts](../README.md#layouts). For the
function signatures, see
[Python API → `lith.layout`](reference-python-api.md#lithlayout).

---

## Why a vocabulary instead of coordinates

Lith never draws anything. It writes a prompt and hands it to a model, so a
layout can only ever be a *description* — a phrase precise enough that the model
composes the frame we meant.

That makes the design problem a writing problem. "Two columns" is a phrase a
model honours reliably. "Panel 3 at x=512, y=880" is not, because the model has
no coordinate system to honour it with. So the vocabulary is a fixed set of
named arrangements, each one a sentence tuned until models render it
consistently.

The sentences are longer than they look. `zigzag` began as *"alternating left
and right, each panel offset and rotated a degree or two"* and models drew
tilted boxes in a column — technically obedient, visually wrong. It now says
*"never in columns,"* pushes each panel to an opposite **edge**, raises the tilt
to 6–10°, and adds diagonal connectors. The word count went up because the
earlier phrasing left a wrong reading available.

## The four inputs

Four things decide the arrangement, in descending precedence:

1. **`brief.layout`** — an explicit name. Always wins.
2. **Content shape** — how many panels there are.
3. **Frame orientation** — portrait or landscape.
4. **A fallback** — `two-column`, for counts nothing else claims.

Only the first is a decision a human makes. The rest are derivations, and they
exist because most briefs shouldn't have to think about layout at all. A brief
that says nothing gets a sensible grid; a brief with something specific to say
says it.

Orientation matters more than it sounds. Three columns of body copy in a 2:3
portrait frame is where legibility dies first — the measure drops below
something readable at thumbnail size, which is the size most of these images are
actually seen at. So column counts cap at two in portrait, and the same panel
count resolves differently depending on the frame:

| Panels | Portrait | Landscape |
|---|---|---|
| 3 | `hero` | `three-column` |
| 6 | `grid-2x3` | `grid-3x2` |
| 7–9 | `two-column` | `grid-3x3` |

The derivation is deterministic. Same recipe, same prompt, every time — no
randomness anywhere in lith, because a recipe that renders differently on
Tuesday is not a recipe.

## What the arrangements are for

Fifteen names, and they are not fifteen flavours of grid. They fall into groups
by the *relationship between panels* they imply:

**Grids** — `stack`, `two-column`, `three-column`, `grid-2x2`, `grid-2x3`,
`grid-3x2`, `grid-3x3`. Panels are peers. Nothing outranks anything. This is the
right default and the wrong choice whenever the content has a shape.

**Emphasis** — `hero`, `sidebar`. One panel outranks the rest. `hero` puts it on
top at double height; `sidebar` runs it down the left edge as a rail. Reach for
these when one section is the claim and the others are support.

**Sequence** — `timeline`, `diagonal`. Order is load-bearing. A timeline's spine
and stubs say *these happen in this order*; a grid says nothing of the kind. If
the headings are numbered steps, a grid is throwing away information the reader
needs.

**Relational** — `radial`, `split`. `radial` rings the panels around a centred
drawing, which is the only arrangement where the diagram is structurally
necessary rather than decorative — it is what the panels point at. `split`
divides two groups across one strong rule, for comparisons.

**Editorial** — `masonry`, `zigzag`. Deliberately asymmetric. These exist because
`styles.json` has declared `prefer_asymmetric_composition: true` since the
beginning while the code produced nothing but symmetric grids. A poster that
reads as a table reads as a table; sometimes that is not what you want.

The grouping is the useful part. Choosing a layout is really choosing what
relationship you are claiming between your sections, and most of the time the
content already knows: numbered steps want `timeline`, a hub with satellites
wants `radial`, a comparison wants `split`.

## Why the layout block is aesthetically neutral

`format_layout` describes structure and nothing else — counts, sizes, columns,
alignment. It never says what a panel *looks like*. That belongs to the family
template, which knows a panel is a HUD block outlined in cyan, or a
double-ruled box on sepia paper, or a die-cut sticker.

The split was not there originally, and the original arrangement was the one
that broke. `format_layout` used to say "hand-drawn boxes" and "Cooper Black" —
manga vocabulary, because the manga family was the first one built. Copied to
the other six, family B would have been asked for hand-drawn Cooper Black inside
a mission-control HUD.

The same failure has a mirror image, and family F had it: its template said
*"each section panel is a column separated by a thin black rule."* That is an
arrangement claim living in a family, and it silently overrode roughly ten of
the fifteen layouts. Neither half may reach into the other. Structure is shared;
appearance is per-family.

## The instruction/content boundary

The layout block sits in the same prompt as the order to reproduce the copy
block character for character. That proximity caused the sharpest bug in the
system's history.

`format_layout` used to emit `TITLE BLOCK —`, `4 SECTION PANELS`,
`DIAGRAM PANEL`, `FOOTER`. Three of seven families lettered those strings into
real images as visible headings. The model could not tell scaffolding from copy,
which is a reasonable confusion: both were text, and one of them came with an
emphatic instruction to render text exactly as written.

Three changes fixed it, and all three are about the same boundary. Zone notes
became lowercase prose that cannot be mistaken for headings. Every template
gained an explicit line saying the notes are directions, not content. And the
diagram description moved out of the copy block into the layout block, because a
diagram is *described* rather than quoted — leaving it among the literal copy is
what made one family letter "A central cloud" inside the drawing.

That last move bought an invariant worth stating plainly: **everything in the
copy block is printed; nothing else is.** Before, the block held a mix of text
to render and text describing a picture, and no rule could tell them apart.

## What this does not do

Lith cannot verify that a layout landed. It writes a description and publishes
whatever comes back; nothing measures panel positions in the returned image. A
model that ignores `grid-3x3` and draws a column produces a perfectly valid
publish. Checking is a human looking at candidates, which is
[stage 4](explanation-pipeline.md#what-runs-and-what-doesnt) and deliberately
unbuilt.

It does now verify the *frame* the arrangement was composed for.
`lith-plate --strict` measures the published image and exits non-zero when the
delivered ratio differs from the request, because a `zigzag` composed for `2:3`
rendered into `16:9` has not landed whatever its panels are doing. That is a
precondition for the arrangement being right, not evidence that it is.

**Panel count is also a legibility decision, not only a compositional one.**
`grid-3x3` in a landscape frame gives each panel roughly a tenth of the frame,
and small text degrades before anything else does — see
[About the design language → Failure modes](explanation-design-language.md#failure-modes).
An arrangement that reads beautifully at nine panels and 2k can garble at nine
panels and 1k.

There is also no layout that positions a specific section. You can say "the
first panel anchors the composition" via `hero`; you cannot say "put THE MESH in
the bottom-left." Arrangements order panels as a set, in brief order.

## See also

- [About output styles](explanation-output-styles.md) — how the seven families
  render the same arrangement differently
- [About the pipeline](explanation-pipeline.md) — why the copy is written down
  before the model sees it
- [README → Layouts](../README.md#layouts) — the key table
