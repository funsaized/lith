# Engineering audit

## System understanding

Lith is a synchronous, standard-library-only Python pipeline with three console
entry points: `lith-plate`, `lith-press`, and `lith-print`. There is no database,
server, background worker, or in-process shared cache.

Recipes are validated into a `Recipe`, then rendered using bundled JSON style
families. Aspect resolution runs from explicit input through content shape and
family defaults to model capability clamping. Layout instructions and literal
poster copy are composed separately. The rendering core is guarded by an AST
import-boundary test that excludes CLI and networking dependencies.

`lith-press` renders a recipe into an `ImageRequest`, resolves credentials from
four read-only tiers, dispatches to a provider adapter, and writes candidate
images. Adapters own provider request and response shapes; `call.http` owns
JSON transport, retry, and error mapping. `lith-print` independently validates a
selected local or downloaded image, measures aspect drift, and publishes bytes
under a deterministic family/headline filename. Strict mode deliberately
publishes the evidence before returning failure for aspect drift.

State is mostly explicit request/result data and filesystem artifacts. The
principal concurrency boundary is multiple CLI processes sharing output paths.
`expand_brief` is an optional subprocess integration whose generated JSON feeds
the same recipe validation boundary.

## Prioritized findings and changes

No critical defect was established in this pass.

| Severity | Finding | Action |
|---|---|---|
| High | Ordinary urllib authorization headers are copied to redirected requests, potentially disclosing provider credentials to another host. | Authorization and proxy authorization now use unredirected headers. Tests exercise the real redirect handler for 301/302/303 responses without network access. |
| High | Download iteration reads lines, allowing an arbitrarily large newline-free allocation before checking the advertised 25 MiB ceiling. | Read at most 64 KiB per call and at most one byte beyond the total ceiling. Regression test checks actual stream consumption. |
| High | PNG validation materialized unrestricted zlib output. | Validate in bounded chunks, discard decoded data, enforce a 256 MiB output ceiling, and reject incomplete or trailing compressed data. Tests cover expansion, large valid images, and split IDAT streams. |
| High | Publishers shared a deterministic `.part` file; candidate writes directly truncated destinations. Concurrent runs could publish another run's bytes or fail on a removed staging file. | Share a per-file atomic writer using unique temporary files. Validate and inspect publication bytes in memory, eliminating a redundant filesystem read. Tests force overlapping replacements, write failure, and rename failure. |
| High | Diagnostic redaction recognized a full authorization value but missed bare tokens echoed in errors. | Redact both forms, including MiniMax status fields. Tests cover HTTP, transport, and application errors. Raw payloads are intentionally retained. |
| Medium | WebP chunk iteration silently returned already-yielded chunks when later framing was malformed. | Parse the full chunk sequence before exposing it; reject malformed tails during validation and size inspection. |
| Medium | Aspect parsing admitted NaN, infinity, negative components, and overflow/underflow. Unhashable recipe selector values raised incidental TypeErrors. | Require finite positive components and quotient; check selector types before dictionary membership. Preserve ValueError-based recipe diagnostics. |
| Medium | HTTP error response bodies were read without explicit closure before retry. | Close HTTPError responses with a context manager; test closure. |

Prompt templates, provider endpoints, capability tables, candidate numbering,
public filenames, and strict-mode exit semantics were not changed. No runtime
dependency was added. README and pipeline/API documentation describe the new
resource and filesystem guarantees.

## Validation

- Baseline: 386 deterministic tests passed.
- Final: 421 deterministic tests passed; three paid live-provider tests excluded.
- Capability coverage: recipe generation 91.0%, provider invocation 93.5%,
  output validation 84.7%; all exceed the required 80% branch-aware threshold.
- `git diff --check`, source compilation, and Python 3.10 AST syntax parsing
  passed for all 20 source modules. This is not runtime testing on Python 3.10.
- Commands used `PYTHONPATH=src .venv/bin/python` because the existing editable
  installation points to the repository's former location.
- Offline wheel/sdist build could not resolve uncached `setuptools` and `wheel`
  in a writable temporary uv cache. Packaging remains unverified.
- No lint or static type checker is configured or installed.
- Follow-up live smoke test, explicitly authorized by the user: all three
  provider canaries passed (xAI, OpenAI, MiniMax). Each requested one image;
  returned bytes, dimensions, and metadata passed the canary assertions.
  Artifacts were retained locally under `outputs/audit-canaries/` (gitignored).
- The generated xAI image also passed `lith-print --strict`, exercising
  validation and atomic publication. No deployment or external image
  publication was performed.

## Remaining opportunities

1. **High: retry semantics for paid generation.** `post_json` retries HTTP 429
   and 5xx once, without an idempotency key. An ambiguous server failure could
   already represent completed work. Preserve the existing tested contract in
   this patch; a follow-up should establish provider-specific retry guarantees
   and expose enough request identity to diagnose duplicate work.
2. **High: response and image trust boundaries.** Provider JSON bodies and local
   files are read whole; base64 adapter results do not pass the same validation
   as URL results until candidate publication. JPEG/WebP checks are not complete
   decoders, and PNG scanlines are not validated against every header rule.
   Choose supported image/response limits and malformed-response policy before
   extending these checks. The new PNG ceiling is not a total RSS bound.
3. **High in a hosted service: URL destinations.** HTTP(S) filtering does not
   prevent requests to private addresses, and final-scheme inspection happens
   after redirect handling. Current usage is an operator-driven CLI. Reuse in
   a service accepting untrusted URLs needs destination/redirect enforcement
   appropriate to its network boundary.
4. **Medium: provider response consistency.** Empty image arrays can produce a
   successful empty result. Base64 parsing, MIME selection, revised prompts,
   and optional reported strings are duplicated. Some adapters populate
   `model_reported` from the requested model when no report exists. Decide the
   public result contract before consolidating parsing or changing these facts.
5. **Medium: capability ownership and typing.** Model identities and limits are
   repeated across aspect data, CLI choices, and adapters. `render_prompt`
   annotates `dict[str, str]` despite nullable notes; several recipe/adapter
   boundaries use untyped dictionaries. Typed result mappings and a single
   dependency-safe capability registry would make future changes safer.
6. **Medium: CLI failure and documentation consistency.** Input/file/credential
   failures often escape as tracebacks, whereas provider failures return 1.
   Contributor instructions about warning streams and exit codes differ from
   actual tested behavior. Document the current contract before standardizing it.
7. **Medium: reproducible validation.** No CI workflow or configured lint/type
   gate exists, and version classifiers are not a runtime compatibility matrix.
   Add clean-install tests, wheel resource/entry-point smoke tests, and supported
   Python versions in a separate tooling change.
8. **Low: oversized names and immutable ownership.** Headline-derived filenames
   are unbounded, and recipes retain mutable caller-owned brief mappings.
   Investigate filename compatibility and caller mutation expectations before
   changing either behavior.

## Risk assessment

Review the 256 MiB PNG expansion ceiling and owner-only permissions inherited
from temporary files: very large PNGs are newly rejected, and published file
permissions may differ from previous artifacts. Atomic replacement changes file
identity and does not preserve ACLs or other metadata. Redirected requests no
longer receive credentials, including same-host redirects.

Publication is atomic per file, not per candidate batch. Deterministic filename
collisions remain last-writer-wins by design; there is no fsync or power-loss
durability guarantee. Abrupt process termination can leave a private temporary
file. Raw provider payloads and exception causes are diagnostic evidence and
may contain sensitive provider-supplied content; redacted error strings do not
make those raw objects safe to log indiscriminately.
