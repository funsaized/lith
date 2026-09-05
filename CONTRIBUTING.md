# Contributing to lith

Three things get contributed here: the **CLI**, the **provider adapters**, and
the **style families and output types**. Each has a contract that already
exists in the code — this file names it so you can tell whether your change
fits inside it or is asking to change it. Both are welcome; they just need
different pull requests.

---

## Ground rules

These are enforced by tests, not by review taste.

| Rule | Enforced by |
|---|---|
| Standard library only — no vendor SDKs, no HTTP clients, no external binaries | review; every dependency in `pyproject.toml` is test-only |
| Python 3.10+ — no syntax newer than the floor in `requires-python` | CI runs Python 3.10 and 3.14 in `.github/workflows/validate.yml` |
| Prompt-side modules never import `lith.cli`, `lith.call`, or a network module | `tests/test_lith_layering.py` (AST import-graph guard) |
| Every capability stays at or above 80% branch-aware coverage | `tests/check_capability_coverage.py` |
| The authored prompt reaches the provider verbatim | `tests/test_lith_<provider>.py` |

The stdlib-only rule is the load-bearing one. It is why the adapters speak raw
JSON over `urllib`, why `hermes_active_model` parses one nested YAML scalar by
hand instead of importing a YAML library, and why lith installs into any Python
3.10 environment with no wheel to build. A PR that adds a runtime dependency
needs to argue that case first, in an issue.

## Setup

```bash
uv pip install -e ".[test]"
uv run pytest
```

```
475 passed, 3 skipped
```

No credentials and no network. The three skips are the live provider canaries;
they run only when you authorize the spend explicitly, and a populated API key
does not enable them. Before opening a PR:

```bash
uv run pytest
uv run python tests/check_capability_coverage.py
```

---

## Contributing to the CLI

Three commands, one per stage of the lithographic sequence, in this order:

| Command | Module | Does |
|---|---|---|
| `lith-plate` | `src/lith/cli/plate.py` | Renders a brief into a prompt and a press envelope. No network. |
| `lith-press` | `src/lith/cli/press.py` | Calls a provider for candidate images. Spends money. |
| `lith-print` | `src/lith/cli/print.py` | Validates the chosen frame and publishes it. |

**A fourth command needs a fourth stage.** Candidate scoring, calendar
rotation, and post-to-brief ingestion are all named in the README's status
table as unbuilt or out of scope — those are stage arguments, and belong in an
issue before a PR. A flag on an existing command is almost always the smaller
correct change.

What to preserve when you touch one:

- **Exit codes are the API.** `0` success, `2` argparse error, and `1` only
  where a command already documents a soft-failure mode (`lith-print --strict`).
  Sweep scripts scrape these; changing one is a breaking change.
- **Human output and `--emit-json` carry the same facts.** If you add a field
  to one, add it to the other.
- **Warnings go to stdout as `[warn]` lines and do not change the exit code**
  unless a strict flag opts in. A person reading output and a script scraping
  exit codes need different things from the same run.
- **Nothing is written in a preview mode.** `lith-plate` without `--press`,
  `lith-press --dry-run/--check/--auth`, and `lith-print` with no image source
  all print and exit without touching the filesystem or the network.
- **Secrets never print.** `--auth` reports tier, source, and fingerprint;
  `--dry-run` prints the request body with the `Authorization` header redacted.
  There is no flag that prints a key.

Tests live in `tests/test_lith_cli_plate.py`, `tests/test_lith_cli_press.py`,
and `tests/test_lith_cli_print.py`. Flag handling is tested in-process; exit
codes and stdout are tested through `python -m lith.cli.<command>` subprocesses,
because that is how a user reaches them.

Update the matching README section (`### lith-plate` / `lith-press` /
`lith-print`) in the same PR. The flag tables there are reference documentation,
so every flag needs a row with its type, default, and effect.

## Contributing a provider

A provider is one module at `src/lith/call/<provider>.py`. It translates the
uniform `ImageRequest` into that vendor's request body and its response back
into a `CallResult`. Nothing above it knows the vendor exists.

**The adapter contract** — `lith.call.generate` and `lith-press --dry-run` both
reach for these by name:

| Name | Kind | Contract |
|---|---|---|
| `GENERATIONS_URL` | `str` | The generations endpoint. Read by `--dry-run` to show the route. |
| `build_request(request, **options)` | `-> dict` | The exact JSON body. Raises `InvalidRequest` on anything the vendor will reject. |
| `unsupported_fields(request)` | `-> dict[str, str]` | Every supplied uniform field this vendor drops, mapped to why. |
| `generate(request, *, credential=None, **options)` | `-> CallResult` | Posts and parses. |

**Register it in four places.** An adapter nobody routes to is dead code:

1. `src/lith/call/capability.py` — `MODEL_PROVIDERS`, one entry per model id.
2. `src/lith/aspect.py` — `MODEL_ASPECTS`, the ratios the model actually
   accepts, so `nearest_supported` can clamp instead of letting the vendor
   silently substitute one.
3. `src/lith/call/creds.py` — `PROVIDERS`, the strict env var name and the
   base-URL prefix its credentials must match.
4. `.env.example` — the same variable name, so the four-tier lookup documents
   itself.

Rules that are not negotiable, because each one exists after a real failure:

- **Never mutate the authored prompt.** Not to fit a cap, not to strip
  characters. Raise before the call and name the measured value and the limit —
  MiniMax's `PROMPT_MAX_CHARS` check is the pattern. Silently truncating a
  poster spec produces an image that looks fine and says the wrong thing.
- **Raise before spending.** Every precondition — `n` range, resolution
  vocabulary, prompt length, `aspect == "auto"` — is checked in `build_request`,
  which runs before any socket opens.
- **Report, do not swallow, what the vendor changed.** A substituted ratio goes
  in `aspect_reported`, a rewritten prompt in `revised_prompt`, a dropped field
  in `unsupported`. `lith-print --strict` is the last line of defense, not the
  only one.
- **Keep the raw payload.** `CallResult.raw` is what makes a surprise
  diagnosable without a second paid call.

**Tests.** Add `tests/test_lith_<provider>.py` covering the request body, every
`InvalidRequest` precondition, response parsing, and the vendor's error shape —
all offline, with the transport stubbed. Then wire the module into
`provider-invocation` in `tests/check_capability_coverage.py`, or the new code
lands outside the gate that is supposed to be measuring it.

A live canary in `tests/test_live_providers.py` is optional and needs its own
`live_<provider>` marker registered in `pyproject.toml`. It must stay behind
`LITH_RUN_LIVE_PROVIDER_CANARIES=1`; nothing that spends money runs by default.

## Contributing styles and output types

**Style families** live in `src/lith/data/styles.json`, keyed `A_sticker`
through `G_log`, with the letter mapping in `recipe.py:FAMILY_KEYS`. The family
object's fields and which of them `render_prompt` actually reads are documented
in the README's [`styles.json` schema](README.md#stylesjson-schema) — `best_for`
and `iconography` are documentation, and no code reads the top-level `rules`
block.

Changing a family's `prompt_template` changes every image anyone generates with
it. That is fine — it is what the file is for — but say so in the PR, and check
the template still renders across the testbed:

```bash
uv run pytest tests/test_integration_recipes.py
```

A **new family** is a bigger change than it looks: a `FAMILY_KEYS` letter, a
full family object, integration recipes under `recipes/integration/` proving it
renders at more than one aspect and layout, and a row in the README's style
table. Open an issue first — seven families that each mean something distinct
beats an eighth that overlaps two of them.

**Layouts** are the arrangement vocabulary in `src/lith/layout.py`, substituted
into `{layout}`. A new arrangement needs an integration recipe that uses it,
because the only real test of a layout is whether a model can follow it.

**Output types** are the image containers `lith` will publish. Adding one means
teaching `src/lith/imagebytes.py` to recognize its magic bytes and report its
extension and dimensions — `lith-print` sniffs the container from the bytes and
never trusts the model id or the URL. It also means a complete real file of
that container in `tests/`, plus truncated and corrupt variants, because the
validator's whole job is rejecting the malformed ones. Nothing is ever
re-encoded; lith publishes the bytes the provider returned.

---

## Documentation

Docs are structured by [Diátaxis](https://diataxis.fr/), and a change usually
belongs in exactly one of them:

| You changed | Update |
|---|---|
| A flag, an exit code, a schema field | `README.md` reference sections |
| A function signature or return shape | `docs/reference-python-api.md` |
| Test layout, markers, coverage gates | `docs/reference-testing.md` |
| Why a boundary sits where it does | the relevant `docs/explanation-*.md` |
| The path a newcomer walks | `docs/tutorial-first-image.md` |

If a change makes the tutorial wrong, it is not done. That path has to work
end to end with no API key.

## Commits and pull requests

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
`docs:`, `refactor:`, `test:`, `chore:`, with an optional scope like
`test(live):`. Subject in the imperative, under 72 characters. The body
explains why; the diff already shows what.

Fill in `.github/pull_request_template.md`, keep unrelated changes in separate
PRs, and say plainly if you did not run the live canaries — nobody expects you
to spend money to contribute.

Contributions are accepted under the MIT license, same as the rest of the
project.
