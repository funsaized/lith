"""Offline by default; explicitly budgeted live provider validation (stdlib only)."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
from unittest.mock import patch
from uuid import uuid4

from lith.call import ImageRequest, generate
from lith.call.creds import resolve_credential
from lith.cli.press import _write_candidates, request_preview
from lith.imagebytes import image_size
from lith.recipe import load_recipe, recipe_from_brief
from lith.render import render_prompt


def plan(manifest: Path, selected: list[str] | None = None) -> list[dict]:
    cases = json.loads(manifest.read_text())
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest must be a nonempty array of cases")
    names = set()
    planned = []
    for case in cases:
        if not isinstance(case, dict) or case.keys() - {"name", "recipe", "options"}:
            raise ValueError("case allows only name, recipe and options")
        name = case.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise ValueError("case name must be a lowercase filename-safe identifier")
        if name in names:
            raise ValueError(f"duplicate case: {name}")
        names.add(name)
        if selected and name not in selected:
            continue
        if not isinstance(case.get("recipe"), str):
            raise ValueError(f"{name}: recipe must be a path")
        source = (manifest.parent / case["recipe"]).resolve()
        original = load_recipe(source)
        options = case.get("options", {})
        if not isinstance(options, dict) or options.keys() - {
            "model", "aspect", "n", "seed", "resolution", "quality",
        }:
            raise ValueError(f"{name}: unknown request options")
        brief = dict(original.brief)
        if "aspect" in options:
            brief["aspect"] = options["aspect"]
        recipe = recipe_from_brief(
            brief, style=original.style, name=name,
            model=options.get("model", original.model), n=options.get("n", original.n),
        )
        rendered = render_prompt(recipe)
        request = ImageRequest(
            prompt=rendered["prompt"], model=recipe.model, n=recipe.n,
            aspect=rendered["aspect_ratio"], negative_prompt=rendered["negative_prompt"],
            **{key: options[key] for key in ("seed", "resolution", "quality") if key in options},
        )
        planned.append(dict(name=name, source=source, recipe=recipe, request=request,
                            preview=request_preview(request)))
    if selected and set(selected) - names:
        raise ValueError(f"unknown selected cases: {sorted(set(selected) - names)}")
    return planned


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def run_case(case: dict, folder: Path) -> dict:
    folder.mkdir()
    request = case["request"]
    write_json(folder / "recipe.json", asdict(case["recipe"]))
    write_json(folder / "request.json", case["preview"])
    record = dict(case=case["name"], requested_model=request.model,
                  requested_n=request.n, requested_aspect=request.aspect,
                  returned_n=None, model_in_raw_payload=None, images=[],
                  http_post_attempts=0, http_retries=0, structural_pass=False)
    original_open = urllib.request.urlopen

    def tracked_open(req, *args, **kwargs):
        if isinstance(req, urllib.request.Request) and req.get_method() == "POST":
            record["http_post_attempts"] += 1
        return original_open(req, *args, **kwargs)

    try:
        credential = resolve_credential(case["preview"]["provider"], recipe_path=case["source"])
        with patch("urllib.request.urlopen", tracked_open):
            result = generate(request, credential=credential)
        record.update(
            returned_n=len(result.candidates), model_in_raw_payload=result.raw.get("model"),
            model_reported_by_adapter=result.model_reported, usage=result.raw.get("usage"),
            cost=result.cost, unsupported=result.unsupported,
        )
        paths = _write_candidates(result, output_dir=folder / "candidates",
                                  family_key=case["recipe"].family_key,
                                  headline=case["recipe"].brief["headline"])
        for candidate, path in zip(result.candidates, paths):
            completed = subprocess.run(
                [sys.executable, "-m", "lith.cli.print", "--recipe", str(folder / "recipe.json"),
                 "--image-file", str(path), "--output-dir", str(folder / f"published-c{candidate.index}"),
                 "--strict"], capture_output=True, text=True,
            )
            # Publication is local; never retain provider response bodies or auth headers.
            (folder / f"publish-c{candidate.index}.log").write_text(completed.stdout + completed.stderr)
            record["images"].append(dict(
                path=str(path.relative_to(folder)), mime=candidate.mime,
                dimensions=image_size(candidate.data), strict_exit=completed.returncode,
                visual_review={"status": "not_reviewed", "findings": []},
            ))
        record["structural_pass"] = (
            len(result.candidates) == request.n
            and all(item["strict_exit"] == 0 for item in record["images"])
        )
    except Exception as exc:
        # Exception messages and raw payloads can contain echoed credentials.
        record["error_type"] = type(exc).__name__
    record["http_retries"] = max(0, record["http_post_attempts"] - 1)
    write_json(folder / "result.json", record)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--case", action="append", help="Select a named case; repeat as needed")
    parser.add_argument("--live", action="store_true", help="Authorize paid generation")
    parser.add_argument("--max-candidates", type=int, help="Required live budget, including transport retries")
    parser.add_argument("--out", type=Path, help="New artifact directory (default: ignored outputs/validation/<id>)")
    args = parser.parse_args(argv)
    try:
        cases = plan(args.manifest, args.case)
        total = sum(case["request"].n for case in cases)
        # Transport retries HTTP 429/5xx once. Budget both potentially billable attempts.
        maximum = total * 2
        if args.max_candidates is not None and args.max_candidates < 1:
            raise ValueError("candidate budget must be positive")
        if args.live and (args.max_candidates is None or maximum > args.max_candidates):
            raise ValueError(f"live run requires --max-candidates >= {maximum} (includes one possible retry per case)")
        if not args.live:
            print(json.dumps(dict(mode="offline", requested_candidates=total,
                                  maximum_with_retries=maximum,
                                  cases=[dict(name=c["name"], request=c["preview"]) for c in cases]), indent=2))
            return 0
        root = (args.out or Path("outputs/validation") / uuid4().hex).resolve()
        root.mkdir(parents=True, exist_ok=False)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    records = []
    for case in cases:
        records.append(run_case(case, root / case["name"]))
        write_json(root / "results.json", records)
    print(json.dumps(dict(artifacts=str(root), results=records), indent=2))
    return 0 if all(record["structural_pass"] for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
