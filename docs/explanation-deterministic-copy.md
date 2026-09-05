# Deterministic copy output

Image-provider frame checks cannot establish text fidelity. The family B prompt
improvement passed four reviewed samples, but a model may still omit, repeat or
invent lettering. `lith-print --svg` provides an explicit offline alternative:
authored text becomes SVG text elements, with no image model in the copy path.

```bash
lith-print --recipe recipes/deterministic.json --svg --output-dir outputs/svg
```

This is a text poster renderer, not an image compositor. It produces one SVG
with a black ground, cyan stacked panels and red square body markers. It does
not alter or cover lettering in a generated image. The existing JPEG/PNG/WebP
publication path still copies validated provider bytes unchanged.

## Implementation decision

| Approach | Exact-copy boundary | Cost and limitations |
|---|---|---|
| Standalone SVG, implemented | Authored strings become escaped XML text; deterministic coordinates and advance widths | Standard library only. Selectable text and scalable output. Font shapes vary by viewer; SVG may need conversion for a destination that accepts only raster images. |
| Raster compositor, deferred | A pinned shaping/rasterization engine draws authored text using bundled fonts | Needs a rendering dependency or external executable, versioned font files, redistribution/license review and platform packaging. Copy becomes pixels, so retain a source/manifest for verification. |

The SVG path is deliberately separate from provider templates. No provider
model or account configuration changes. No rasterization dependency is added.
No third-party font is shipped, so there is no new font redistribution license;
renderer code uses the repository's MIT license. A later font bundle must
include the chosen font's own license and permitted redistribution terms.

## Supported contract

- Family B and `layout: "stack"` or omitted; standard prompt mode only.
- Title (`title` overrides `headline`), optional subtitle/footer, and section
  headings/body lines. Input order and intentional repetitions are preserved.
- Printable ASCII display values, including spaces and XML punctuation.
  Unicode, tabs and embedded newlines fail explicitly. This avoids promising
  shaping, bidirectional text or fallback-glyph behavior without a font contract.
- Width 1200; supported ratios `1:1`, `2:3`, `3:2`. Omitted/`auto` aspect uses
  `2:3` for three or more sections, otherwise `1:1`. This is an SVG canvas rule,
  independent of provider aspect limits and prompt templates.
- `model` and `n` remain validated recipe fields, but do not change the SVG or
  cause a provider call. `topic` and `icon` are context fields; no icon is drawn.
- Diagrams, diagram positions, other layouts/families, palette/volume overrides,
  compact mode and unknown fields fail instead of being discarded. In
  particular, the original dense dill-pickle recipe is rejected because its
  drawing cannot be interpreted deterministically from natural language.

Every field is wrapped separately, preferring spaces and splitting long tokens
when necessary. Wrapping does not trim spaces, hyphenate, normalize punctuation
or insert characters. Each `text[data-copy]` element contains consecutive
`tspan` values whose concatenation exactly equals the authored field. Its key
identifies the source, for example `sections/0/lines/1`. Structural identifiers
are attributes, never visible text. XML metacharacters are escaped by the
standard-library serializer, and there are no external images, scripts, styles
or font requests in generated SVGs.

Fixed font sizes, line heights and `textLength`/`lengthAdjust` advance widths
define the layout without installed font-metric queries. Text stays at readable
sizes; excess vertical content raises an error before any file is written.
It does not shrink until unreadable, silently truncate, or change the aspect.
Glyph shapes and ink extents still depend on the viewer's monospace font and
SVG implementation. Exact XML text and deterministic coordinates are guaranteed;
identical raster pixels across engines are not.

## Publication and verification

`--svg` is mutually exclusive with `--image-file` and `--image-url`. Successful
rendering writes `B_brutalist_<headline>.svg` atomically, warns on overwrite and
exits 0. Unsupported content/overflow exits 2 and preserves an existing output.
`--strict` adds no check to this mode: frame dimensions are constructed, and
overflow is always an error. Existing source-image mode retains its original
strict frame behavior. Supplying arbitrary SVG through `--image-file` is still
rejected; SVG is not added to the trusted raster-image input formats.

Use `from lith.svg import render_svg` with a validated `Recipe` for the same
offline serializer; it returns UTF-8 bytes and raises `ValueError` for unsupported
content or overflow. The CLI does not run prompt rendering, credential lookup,
provider generation or rasterization in this mode.

`tests/test_lith_svg.py` checks byte repeatability, exact decoded copy, escaping,
wrapping, title precedence, repetitions, frame bounds, provider independence,
unsupported inputs, and failed publication preserving previous bytes. The
output-validation coverage gate includes this module, and installed-wheel CI
checks the SVG CLI outside the checkout. These checks verify source text and
layout advances; visual inspection remains useful for a particular SVG viewer.

## Evaluation and next boundary

The shipped example exercises three dense sections and punctuation in a
landscape frame; square, portrait and wrapping examples are also evaluated
offline. Local previews use an already-installed `rsvg-convert`, outside Lith's
runtime path. Retained evaluation artifacts live under
`outputs/deterministic-evaluation/` and are not committed.

For diagrams, the next design needs explicit nodes, labels and edges rather
than an inferred interpretation of natural-language instructions. For identical
PNG exports, first choose a font license and pinned rasterization engine, then
test glyph coverage, metrics, line breaks, bounds and pixels in that controlled
environment. Neither should become a silent fallback on provider output.
