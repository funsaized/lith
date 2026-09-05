# Testing reference

Complete description of lith's test suite: how it is invoked, what selects and
deselects, which module covers what, and the thresholds that gate a change.

For running the suite once as a new cloner, see
[README → Tests](../README.md#tests). For why the pipeline is testable where it
is, see [About the pipeline](explanation-pipeline.md).

---

## Contents

- [Invocation](#invocation)
- [Markers](#markers)
- [Environment variables](#environment-variables)
- [Test modules](#test-modules)
- [Capability coverage gate](#capability-coverage-gate)
- [Live provider canaries](#live-provider-canaries)
- [Budgeted provider matrix](#budgeted-provider-matrix)
- [Clean-install CI](#clean-install-ci)
- [Fixtures](#fixtures)
- [Coverage configuration](#coverage-configuration)

---

## Invocation

| Command | Selects |
|---|---|
| `uv run pytest` | Every deterministic test. Live canaries are collected and skipped. |
| `uv run pytest -m integration` | Deterministic cross-module tests only. |
| `uv run pytest -m live_provider` | The three live canaries. Skipped unless authorized — see [Environment variables](#environment-variables). |
| `uv run pytest -m live_xai` | The xAI canary alone. `live_openai` and `live_minimax` select the others. |
| `uv run python tests/check_capability_coverage.py` | The three branch-aware coverage gates. Runs pytest itself; do not invoke under `pytest`. |

The default run requires no credentials and makes no network request.

Run `uv run pytest -q` for the current test count.

The three skips are the live canaries. Their skip reason names the variable that
enables them.

## Markers

Declared in `pyproject.toml` under `[tool.pytest.ini_options]`.

| Marker | Meaning |
|---|---|
| `integration` | Deterministic cross-module integration coverage. |
| `live_provider` | Opt-in test that contacts a real provider and spends money. Applied to each of the three provider canaries. |
| `live_xai` | Opt-in xAI provider canary. |
| `live_openai` | Opt-in OpenAI provider canary. |
| `live_minimax` | Opt-in MiniMax provider canary. |

`live_xai`, `live_openai`, and `live_minimax` are applied in addition to
`live_provider`, never instead of it. Selecting `-m live_provider` selects all
three. The artifact-sink unit test in the same module is unmarked and never
contacts a provider.

## Environment variables

| Variable | Read by | Effect |
|---|---|---|
| `LITH_RUN_LIVE_PROVIDER_CANARIES` | `tests/test_live_providers.py` | Live canaries run only when set to exactly `"1"`. Any other value, or absence, skips them. |
| `LITH_LIVE_OUTPUT_DIR` | `tests/test_live_providers.py` | Optional directory in which validated live candidate images are retained. Without it, candidate bytes stay in memory only. |
| `COVERAGE_FILE` | `tests/check_capability_coverage.py` | Set per capability to a temporary path so the three gates never share coverage data. Not intended to be set by the caller. |

Provider credential variables still participate in ordinary credential
resolution, but do not affect test selection.

```console
$ uv run pytest tests/test_live_providers.py -rs -q
SKIPPED [1] tests/test_live_providers.py:55: set LITH_RUN_LIVE_PROVIDER_CANARIES=1 to authorize real provider calls and spend
```

Credential presence does not enable live tests. A populated `XAI_API_KEY`,
`OPENAI_API_KEY`, or `MINIMAX_API_KEY` has no effect on selection;
`LITH_RUN_LIVE_PROVIDER_CANARIES=1` is the only switch.
This environment switch applies to pytest canaries only. The separate matrix
harness below requires its own explicit `--live` flag and budget.

## Test modules

| Module | Covers |
|---|---|
| `test_lith_svg.py` | Deterministic SVG copy, wrapping, XML escaping, bounds, unsupported content and offline publication. |
| `test_lith_render.py` | `render_prompt`, `format_spec`, `copy_note`, slot substitution, palette resolution. |
| `test_integration_recipes.py` | The 34-recipe testbed under `recipes/integration/`, driven through both prompt-side CLIs in-process. Layout, diagram-position, family, model, and aspect-rung coverage assertions. |
| `test_lith_cli_plate.py` | `lith-plate` argument handling and envelope shape. |
| `test_lith_cli_press.py` | `lith-press` routing, `--check`, `--dry-run`, `--auth`, render-note surfacing, candidate writing. |
| `test_lith_cli_print.py` | `lith-print` publish path, `--strict`, overwrite warning, `aspect_mismatch`. |
| `test_lith_call.py` | `ImageRequest`, `Candidate`, `CallResult`, dispatcher behaviour. |
| `test_lith_creds.py` | Four-tier credential resolution, `base_url` validation, `api_key` pool-entry rejection, missing-key message. |
| `test_lith_http.py` | JSON transport, retry, redaction, and the mapping from HTTP and provider payloads to the error hierarchy. |
| `test_lith_xai.py` | xAI request body, `storage_options`, `unsupported`, response parsing. |
| `test_lith_openai.py` | OpenAI request body, `pixel_size` mapping, provider options, response parsing. |
| `test_lith_compact.py` | Compact rendering, exact prompt-length boundaries, verbatim copy, unsupported fields/families, CLI pre-spend rejection, and unchanged standard prompts. |
| `test_lith_minimax.py` | MiniMax request body, `PromptTooLong` precondition, `base_resp` error mapping, width/height fallback. |
| `test_output_integration.py` | Complete PNG, JPEG, and WebP containers through the output path; truncated and corrupt input rejection. |
| `test_recipe_generation_integration.py` | Brief expansion to rendered envelope, including a subprocess run through the CLI. |
| `test_lith_expand.py` | `expand_brief` and `parse_brief_response`. |
| `test_lith_layering.py` | Import-graph guard. Parses `render`, `aspect`, `layout`, `recipe`, `styles`, and `paths` with `ast` and fails if any imports `lith.cli`, `lith.call`, or a network module. One test, no environment input. |
| `test_lith_smoke_e2e.py` | One end-to-end recipe-to-published-file run. |
| `test_live_providers.py` | The three live canaries. See [Live provider canaries](#live-provider-canaries). |
| `test_provider_matrix.py` | Offline defaults, manifest validation, live budget, retries, failure retention, model provenance and separate visual-review status. All network responses are mocked. |

## Capability coverage gate

`tests/check_capability_coverage.py` runs three independent branch-aware
coverage measurements, one per system capability. Each runs in its own
subprocess with its own `COVERAGE_FILE` in a temporary directory, so no
capability inherits another's coverage.

**Threshold:** `80.0` percent, applied to each capability separately. The script
defines it as `THRESHOLD`.

**Metric:** `(covered_lines + covered_branches) / (num_statements + num_branches)`,
taken from `coverage json` totals. A capability with no measurable statements
scores `100.0`.

| Capability | Source packages | Test modules |
|---|---|---|
| `recipe-generation` | `lith.expand`, `lith.recipe`, `lith.render`, `lith.aspect`, `lith.layout`, `lith.styles`, `lith.paths`, `lith.cli.plate` | `test_recipe_generation_integration.py`, `test_integration_recipes.py`, `test_lith_expand.py`, `test_lith_render.py`, `test_lith_compact.py`, `test_lith_cli_plate.py` |
| `provider-invocation` | `lith.call`, `lith.cli.press` | `test_lith_call.py`, `test_lith_cli_press.py`, `test_lith_creds.py`, `test_lith_http.py`, `test_lith_minimax.py`, `test_lith_openai.py`, `test_lith_xai.py` |
| `output-validation` | `lith.imagebytes`, `lith.cli.print`, `lith.svg` | `test_lith_svg.py`, `test_output_integration.py`, `test_lith_cli_print.py`, `test_lith_smoke_e2e.py`, `test_integration_recipes.py` |

**Output.** One line per capability, then exit `0` when all pass or `1` with a
summary line on stderr naming each failure.

```console
$ uv run python tests/check_capability_coverage.py
PASS recipe-generation: 89.5% branch-aware (428/467 lines, 180/212 branches)
PASS provider-invocation: 93.5% branch-aware (762/800 lines, 257/290 branches)
PASS output-validation: 84.0% branch-aware (204/235 lines, 84/108 branches)
```

A capability whose tests fail is reported as `<name>: tests failed` and its
coverage is not measured.

## Live provider canaries

Three tests in `tests/test_live_providers.py`, one per provider. Each makes
exactly one generation request with `n=1`.

| Test | Model | Aspect | Prompt source |
|---|---|---|---|
| `test_xai_live_canary_…` | `grok-imagine-image-2.0`, `resolution="1k"` | from `recipes/live_test_recipe.json` | `render_prompt` |
| `test_openai_live_canary_…` | `gpt-image-1-mini`, `quality="low"` | from the same recipe | `render_prompt` |
| `test_minimax_live_canary_uses_compact_prompt_under_provider_cap` | `image-01`, `seed=1047` | `1:1` | `recipes/minimax/sparse.json` compact render |

The OpenAI canary pins `gpt-image-1-mini` at `quality="low"` — the cheapest
combination that still exercises authentication, request shape, and response
parsing. It asserts `result.model_reported == request.model`. It does not assert
copy fidelity; that model is
[unsuitable for dense specs](../README.md#not-every-listed-model-can-render-a-dense-spec).

The MiniMax canary renders `recipes/minimax/sparse.json` through the opt-in
compact family B path, then exercises the adapter with `seed=1047`. It asserts
the rendered prompt is below 1500 characters. The three-section example is
covered offline; running its live test is a separate explicit spend.

**Shared assertions.** Each canary checks that one candidate returned, that its
bytes pass `looks_like_image`, that its dimensions are readable and within 2
percent of the requested ratio, and that `raw` is a non-empty dict and
`unsupported` is a dict.

Credentials resolve through the ordinary four-tier chain with
`recipe_path=LIVE_RECIPE`; the canaries do not read credentials any differently
from production code.

### Retaining generated images

By default, validated candidate bytes stay in memory and disappear when pytest
exits. Set `LITH_LIVE_OUTPUT_DIR` to retain them. Add `-s` to show each absolute
path as it is written:

```bash
LITH_LIVE_OUTPUT_DIR=outputs/canaries \
LITH_RUN_LIVE_PROVIDER_CANARIES=1 \
uv run pytest -m live_provider -s
```

The directory is created when needed. Filenames are deterministic:
`{provider}_{model}_canary-c{index}.<jpg|png|webp>`. A later run of the same
provider/model overwrites its previous canary artifact.

## Budgeted provider matrix

`tests/run_provider_matrix.py` reuses the production renderer, request builders,
credential resolver, provider adapters, candidate writer and strict publisher.
It adds no runtime dependency or public CLI. Default execution renders and
validates every selected request offline: no credential lookup, network call,
or artifact write occurs.

```bash
uv run python tests/run_provider_matrix.py tests/provider-matrix.json
uv run python tests/run_provider_matrix.py tests/provider-matrix.json --case xai-portrait
```

The manifest is a nonempty JSON array of objects with a unique filename-safe
`name`, a `recipe` path relative to the manifest, and optional `options`:
`model`, `aspect`, `n`, `seed`, `resolution`, `quality`. Overrides are validated
and applied before rendering. Repeat `--case` to select cases; omission selects
the entire manifest. All selected cases must pass preflight before any spend.

**Paid, explicit opt-in:** append `--live --max-candidates 8` to run the shipped
four-candidate matrix. The budget reserves two attempts per request because
the production transport may retry a 429/5xx once. One selected `n=1` case
therefore needs a budget of 2. This is a candidate-attempt ceiling, not a dollar
limit; provider pricing and billing of failed attempts are outside the harness.
It never generates replacement candidates after a count/frame failure.

Live artifacts go into a new `outputs/validation/<unique-id>` directory, or a
new directory selected by `--out`. Existing directories are rejected to protect
earlier evidence. Generated files and images belong under ignored `outputs/`;
do not commit them. Each case retains the effective recipe, redacted request,
candidate images, strict publication logs, and `result.json`. The aggregate
`results.json` records requested versus returned count, requested model versus
the raw response's actual `model` field (null when absent), the adapter's model
fallback separately, dimensions, strict exit, POST attempts/retries, and usage
or cost when provided. Raw response bodies/base64 payloads and credential
headers are never retained. Failures record their exception type without
potentially secret-bearing exception messages; independent cases still run.

Exit 0 means all counts and strict publication checks passed. **It does not
mean the images passed visual review.** Each image starts with
`visual_review.status = "not_reviewed"`. Inspect the retained image against its
recipe and record `pass` or `fail`, exact omissions/additions/substitutions,
instruction leakage, and expected/observed diagram-label counts. Update the
case and aggregate records together. Wrapping may change; authored words,
punctuation and intentional repetitions must survive. Never infer visual
approval from dimensions or an unsupported agent assertion.

### Retained live evidence (2026-09-05)

The earlier xAI quality/OpenAI GPT-image-2 matrix returned eight candidates with
valid counts and frames; six passed visual copy review. Failures were a repeated
BRINE diagram label in an xAI square batch and printed structural field labels
in the OpenAI landscape image. After standard family B switched to ordered
JSON copy blocks, four authorized `n=1` portrait/landscape candidates (two per
provider) passed strict publication and direct line-by-line visual review, with
four POSTs and no retries. All four diagram labels appeared exactly once in
each. This small sample does not establish general fidelity or retest batches.
Neither provider independently reported a model identifier in these payloads.
Evidence remains local under `outputs/provider-matrix/` and
`outputs/copy-fidelity/`; it is not a CI fixture.

Both earlier MiniMax compact samples had valid frames but failed visual copy
review; compact mode remains experimental. Provider mocks cover supported
request options, but live evidence is limited to the models/options explicitly
recorded above and the individual canaries. It is not exhaustive certification
of every supported model, seed, aspect, quality or resolution.

## Clean-install CI

`.github/workflows/validate.yml` runs Python 3.10 and 3.14 on pushes and pull
requests. Each job installs the test extra in a clean environment, excludes
live tests, runs the three coverage gates, builds an sdist and wheel, and runs
`tests/check_wheel.py dist/*.whl`. Live canaries are also disabled explicitly
in the job environment; credentials are not required.

The wheel smoke creates a fresh temporary venv, installs only the wheel with
`--no-index --no-deps`, removes Python path overrides, and runs outside the
checkout. It checks the installed import location, all three CLI entry points,
packaged standard/compact templates, offline provider preview, and byte-preserving
strict publication of a complete generated PNG, plus deterministic SVG output. Reproduce locally with:

```bash
uv build --out-dir /tmp/lith-dist
uv run python tests/check_wheel.py /tmp/lith-dist/lith-0.1.0-py3-none-any.whl
```

## Fixtures

| Path | Purpose |
|---|---|
| `tests/fixtures/fake_brief_llm.py` | Stands in for the `llm_cmd` subprocess `expand_brief` shells out to, so brief expansion is testable without an LLM. |
| `recipes/integration/*.json` | The 34-recipe testbed. Not a fixture directory, but the input `test_integration_recipes.py` is built around. |
| `recipes/live_test_recipe.json` | The single recipe the live canaries and the end-to-end smoke test use. |
| `outputs/B_brutalist_32_langs_raw.jpg` | The tracked reference image. Used as a stand-in generated image where a test needs real bytes. |

There is no `tests/conftest.py`. Fixtures are declared in the modules that use
them.

## Coverage configuration

Declared in `pyproject.toml`:

```toml
[tool.coverage.run]
branch = true
source = ["lith"]

[tool.coverage.report]
show_missing = true
```

`branch = true` applies to the whole-suite report and to the capability gate,
which passes `--branch` explicitly as well.

```console
$ uv run coverage run -m pytest -q && uv run coverage report
```

`coverage` is supplied by the `test` extra alongside `pytest`; both install with
`uv sync --extra test`.
