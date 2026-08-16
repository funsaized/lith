#!/usr/bin/env python3
"""Call an image provider from a rendered lith recipe."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from importlib import import_module
import json
import os
import pathlib
import sys
from typing import Any

from lith import load_recipe, output_path, render_prompt
from lith.call import CallResult, ImageRequest, generate
from lith.call.capability import provider_for_model
from lith.call.creds import MissingCredential, PROVIDERS, resolve_credential
from lith.call.http import REDACTED, ProviderError
from lith.imagebytes import image_ext
from lith.paths import default_output_dir


HERMES_ASPECTS = frozenset({"16:9", "1:1", "9:16"})


def _yaml_scalar(raw: str) -> str | None:
    """Parse the plain or quoted scalar used for Hermes' model setting."""
    value = raw.strip()
    if not value:
        return None
    if value[:1] in {"'", '"'}:
        closing = value.find(value[0], 1)
        if closing >= 1:
            value = value[1:closing]
    else:
        value = value.split(" #", 1)[0].strip()
    if not value or value.lower() in {"null", "none", "~"}:
        return None
    return value


def hermes_active_model(
    *,
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> tuple[str | None, str]:
    """Read ``image_gen.model`` from Hermes, then fall back to the environment.

    Hermes' file is YAML, but this setting is a single nested scalar.  Keeping
    this deliberately narrow preserves lith's standard-library-only contract.
    """
    home_dir = pathlib.Path(home).expanduser() if home is not None else pathlib.Path.home()
    config = home_dir / ".hermes" / "config.yaml"
    try:
        lines = config.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []
    except OSError as exc:
        raise ValueError(f"cannot read Hermes config {config}: {exc}") from exc

    section_indent: int | None = None
    for raw_line in lines:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if section_indent is None:
            key, separator, value = stripped.partition(":")
            if separator and key.strip() == "image_gen" and not value.strip():
                section_indent = indent
            continue
        if indent <= section_indent:
            section_indent = None
            key, separator, value = stripped.partition(":")
            if separator and key.strip() == "image_gen" and not value.strip():
                section_indent = indent
            continue
        key, separator, value = stripped.partition(":")
        if separator and key.strip() == "model":
            model = _yaml_scalar(value)
            if model is not None:
                return model, "~/.hermes/config.yaml:image_gen.model"

    environment = os.environ if environ is None else environ
    fallback = environment.get("FAL_IMAGE_MODEL", "").strip()
    if fallback:
        return fallback, "FAL_IMAGE_MODEL"
    return None, "not configured"


def routing_decision(
    recipe_model: str,
    resolved_aspect: str,
    *,
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str | None]:
    """Return the inspectable Hermes-versus-lith-call routing decision."""
    hermes_model, source = hermes_active_model(home=home, environ=environ)
    failures: list[str] = []
    if hermes_model is None:
        failures.append(
            "Hermes has no active image model in "
            "~/.hermes/config.yaml image_gen.model or FAL_IMAGE_MODEL"
        )
    elif hermes_model != recipe_model:
        failures.append(
            f"Hermes active model {hermes_model!r} does not match recipe model "
            f"{recipe_model!r}"
        )
    if resolved_aspect not in HERMES_ASPECTS:
        allowed = ", ".join(sorted(HERMES_ASPECTS))
        failures.append(
            f"Hermes image_generate cannot preserve resolved aspect "
            f"{resolved_aspect!r}; it routes only {allowed}"
        )
    if failures:
        route = "lith-call"
        reason = "; ".join(failures)
    else:
        route = "image_generate"
        reason = (
            f"Hermes active model matches {recipe_model!r} and resolved aspect "
            f"{resolved_aspect!r} is one of its three exact buckets"
        )
    return {
        "route": route,
        "reason": reason,
        "hermes_model": hermes_model,
        "hermes_model_source": source,
        "recipe_model": recipe_model,
        "resolved_aspect": resolved_aspect,
    }


def _request_from_recipe(args: argparse.Namespace) -> tuple[Any, dict[str, Any], ImageRequest]:
    recipe = load_recipe(args.recipe)
    rendered = render_prompt(recipe)
    request = ImageRequest(
        prompt=rendered["prompt"],
        model=recipe.model,
        aspect=rendered["aspect_ratio"],
        n=recipe.n if args.n is None else args.n,
        seed=args.seed,
        resolution=args.resolution,
        quality=args.quality,
        negative_prompt=rendered["negative_prompt"],
    )
    return recipe, rendered, request


def request_preview(request: ImageRequest) -> dict[str, Any]:
    """Build the exact offline provider request with authorization redacted."""
    provider = provider_for_model(request.model)
    adapter = import_module(f"lith.call.{provider}")
    try:
        body = adapter.build_request(request)
        url = adapter.GENERATIONS_URL
    except AttributeError as exc:
        raise ValueError(f"{provider} adapter cannot preview generation requests") from exc
    unsupported_builder = getattr(adapter, "unsupported_fields", None)
    unsupported = unsupported_builder(request) if unsupported_builder else {}
    return {
        "provider": provider,
        "method": "POST",
        "url": url,
        "headers": {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {REDACTED}",
        },
        "body": body,
        "unsupported": unsupported,
    }


def _auth_report(recipe_path: pathlib.Path | None) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for provider in PROVIDERS:
        try:
            credential = resolve_credential(provider, recipe_path=recipe_path)
        except MissingCredential as exc:
            report.append({"provider": provider, "status": "missing", "reason": str(exc)})
            continue
        report.append(
            {
                "provider": provider,
                "status": "resolved",
                "tier": credential.tier,
                "source": credential.source,
                "fingerprint": credential.fingerprint,
            }
        )
    return report


def _print_auth(report: list[dict[str, Any]], *, emit_json: bool) -> None:
    if emit_json:
        print(json.dumps(report, indent=2))
        return
    for item in report:
        if item["status"] == "missing":
            print(f"{item['provider']}: missing — {item['reason']}")
        else:
            print(
                f"{item['provider']}: tier {item['tier']} — {item['source']} "
                f"— fingerprint {item['fingerprint']}"
            )


def _result_metadata(result: CallResult, paths: list[pathlib.Path]) -> dict[str, Any]:
    candidates = []
    for candidate, path in zip(result.candidates, paths):
        candidates.append(
            {
                "index": candidate.index,
                "path": str(path),
                "mime": candidate.mime,
                "dimensions": candidate.dimensions,
            }
        )
    return {
        "candidates": candidates,
        "model_reported": result.model_reported,
        "aspect_reported": result.aspect_reported,
        "revised_prompt": result.revised_prompt,
        "unsupported": result.unsupported,
        "cost": result.cost,
        "raw": result.raw,
    }


def _write_candidates(
    result: CallResult,
    *,
    output_dir: pathlib.Path,
    family_key: str,
    headline: str,
) -> list[pathlib.Path]:
    stem = output_path(output_dir, family_key, headline, "")
    planned: list[tuple[pathlib.Path, bytes]] = []
    indexes: set[int] = set()
    for candidate in result.candidates:
        if candidate.index in indexes:
            raise ValueError(f"duplicate candidate index {candidate.index}")
        indexes.add(candidate.index)
        extension = image_ext(candidate.data)
        if extension is None:
            raise ValueError(
                f"candidate {candidate.index} is not a recognized image format"
            )
        path = stem.with_name(f"{stem.name}-c{candidate.index}{extension}")
        planned.append((path, candidate.data))
    output_dir.mkdir(parents=True, exist_ok=True)
    for path, data in planned:
        path.write_bytes(data)
    return [path for path, _ in planned]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate image candidates directly from a lith recipe."
    )
    parser.add_argument("--recipe", type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path, help="Candidate output directory")
    parser.add_argument("--n", type=int, help="Override the recipe candidate count")
    parser.add_argument("--resolution", choices=["1k", "2k"])
    parser.add_argument("--quality", choices=["low", "medium", "high"])
    parser.add_argument("--seed", type=int)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print request; do not call")
    mode.add_argument("--check", action="store_true", help="Print routing decision only")
    mode.add_argument("--auth", action="store_true", help="Inspect credential resolution")
    parser.add_argument("--emit-json", action="store_true", help="Emit machine-readable JSON")
    return parser


def _run(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    if args.auth:
        _print_auth(_auth_report(args.recipe), emit_json=args.emit_json)
        return 0
    if args.recipe is None:
        parser.error("--recipe is required unless --auth is used")

    recipe, rendered, request = _request_from_recipe(args)
    if args.check:
        decision = routing_decision(recipe.model, rendered["aspect_ratio"])
        if args.emit_json:
            print(json.dumps(decision, indent=2))
        else:
            print(f"route={decision['route']}")
            print(f"reason={decision['reason']}")
        return 0
    if args.dry_run:
        print(json.dumps(request_preview(request), indent=2))
        return 0

    provider = provider_for_model(request.model)
    credential = resolve_credential(provider, recipe_path=args.recipe)
    result = generate(request, credential=credential)
    paths = _write_candidates(
        result,
        output_dir=args.out or default_output_dir(args.recipe),
        family_key=recipe.family_key,
        headline=recipe.brief["headline"],
    )
    metadata = _result_metadata(result, paths)
    if args.emit_json:
        print(json.dumps(metadata, indent=2))
    else:
        for path in paths:
            print(f"[done]        {path}")
        for field in ("model_reported", "aspect_reported", "revised_prompt", "cost"):
            value = metadata[field]
            if value is not None:
                print(f"[{field}] {value}")
        for field, reason in result.unsupported.items():
            print(f"[unsupported] {field}: {reason}")
    return 0


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    try:
        return _run(parser, args)
    except ProviderError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
