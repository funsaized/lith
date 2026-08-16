## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## Area

<!-- Delete the sections that don't apply, and the whole block if this is
docs-only. Contracts for each are in CONTRIBUTING.md. -->

**CLI** — `lith-plate` / `lith-press` / `lith-print`

- [ ] Exit codes unchanged (`0` success, `2` argparse, `1` only where a strict flag documents it)
- [ ] Human output and `--emit-json` carry the same facts
- [ ] Preview modes still write nothing: `lith-plate` without `--press`, `lith-press --dry-run/--check/--auth`, `lith-print` with no image source
- [ ] No flag prints a credential
- [ ] New or changed flags have a README row: type, default, effect

**Provider** — `src/lith/call/<provider>.py`

- [ ] Exposes `GENERATIONS_URL`, `build_request`, `unsupported_fields`, `generate`
- [ ] Registered in `capability.py:MODEL_PROVIDERS`, `aspect.py:MODEL_ASPECTS`, `creds.py:PROVIDERS`, and `.env.example`
- [ ] The authored prompt reaches the provider verbatim — preconditions raise instead of truncating
- [ ] Every precondition is checked in `build_request`, before any socket opens
- [ ] Substituted ratios, revised prompts, and dropped fields are reported, not swallowed
- [ ] `tests/test_lith_<provider>.py` added and wired into `provider-invocation` in `tests/check_capability_coverage.py`

**Styles and output types**

- [ ] `styles.json` still matches the schema in the README; family docs updated
- [ ] A changed `prompt_template` is called out below — it changes every image that family produces
- [ ] A new family or layout has integration recipes under `recipes/integration/`
- [ ] A new image container is recognized by `imagebytes.py` from its magic bytes, with complete, truncated, and corrupt fixtures

## Checks

```console
$ uv run pytest

$ uv run python tests/check_capability_coverage.py

```

- [ ] Standard library only — no new runtime dependency
- [ ] Docs updated per the table in CONTRIBUTING.md
- [ ] Live provider canaries: not run / run against <provider>

## Notes for the reviewer

<!-- Anything that changes existing output, breaks a documented contract, or
that you deliberately left out. -->
