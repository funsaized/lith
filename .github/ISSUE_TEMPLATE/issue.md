---
name: Issue
about: Report a bug or propose a change to the CLI, a provider, or a style
title: ''
labels: ''
assignees: ''
---

## Area

<!-- Delete the ones that don't apply. -->

- **CLI** — `lith-plate` / `lith-press` / `lith-print`
- **Provider** — xAI / OpenAI / MiniMax, or a new one
- **Styles and output types** — a family in `styles.json`, a layout, an image container
- **Docs**
- **Other**

## What happened

<!-- For a bug: what you expected, what you got. For a proposal: what today
forces you to do by hand. -->

## Reproduce it

<!-- The command, with keys removed. Preview modes reproduce most issues
without spending anything:

  lith-plate --recipe path/to/recipe.json --press --emit-json
  lith-press --recipe path/to/recipe.json --dry-run
  lith-press --auth
  lith-print --recipe path/to/recipe.json

Paste the recipe if the issue depends on it. `--dry-run` output is already
redacted; `--auth` prints fingerprints, never keys. Check anything you paste
yourself. -->

```console
$ 
```

## Environment

- lith version or commit:
- Python (`python -V`):
- OS:
- Model id, if a provider is involved:

## Anything else

<!-- If the image came out wrong, describing it beats attaching it — but attach
it if the difference is visual. If a provider substituted an aspect ratio,
`lith-print` prints a `[warn]` line naming both ratios; include it. -->
