import json
import pathlib
import re
import sys

import pytest

from lith import load_recipe, render_prompt
from lith.call import CallResult, Candidate, ImageRequest
from lith.call.capability import provider_for_model
from lith.call.creds import Credential
from lith.cli import call as call_cli
from lith.cli.call import request_preview


PROVIDER_VARIABLES = ("XAI_API_KEY", "OPENAI_API_KEY", "MINIMAX_API_KEY")


@pytest.fixture(autouse=True)
def isolated_home_and_credentials(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for variable in (*PROVIDER_VARIABLES, "FAL_IMAGE_MODEL"):
        monkeypatch.delenv(variable, raising=False)


def _recipe(tmp_path, *, model="grok-imagine-image-2.0", aspect="2:3"):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    path = root / "recipes" / "fixture.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "name": "fixture",
                "style": "B",
                "model": model,
                "n": 4,
                "brief": {
                    "topic": "test",
                    "headline": "SHIP",
                    "icon": "gear",
                    "aspect": aspect,
                },
            }
        )
    )
    return root, path


def _main(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["lith-call", *map(str, argv)])
    return call_cli.main()


def _png(width=20, height=30):
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00" * 8
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
    )


def test_dry_run_prints_exact_xai_request_without_auth_or_network(
    tmp_path, monkeypatch, capsys
):
    _, path = _recipe(tmp_path)
    monkeypatch.setenv("XAI_API_KEY", "must-never-appear")

    def forbidden(*args, **kwargs):
        raise AssertionError("dry-run resolved credentials or made a live call")

    monkeypatch.setattr(call_cli, "resolve_credential", forbidden)
    monkeypatch.setattr(call_cli, "generate", forbidden)
    assert _main(
        monkeypatch,
        "--recipe", path,
        "--n", "2",
        "--resolution", "2k",
        "--quality", "high",
        "--seed", "7",
        "--dry-run",
    ) == 0

    output = capsys.readouterr().out
    preview = json.loads(output)
    rendered = render_prompt(load_recipe(path))
    # Advisory notes ride alongside the request; lift them out so the request
    # shape below stays an exact-equality assertion. This fixture brief has no
    # sections, so copy_note must be among them.
    notes = {
        key: preview.pop(key)
        for key in ("aspect_note", "copy_note", "limit_notes")
        if key in preview
    }
    assert "letter template wording" in notes["copy_note"]
    assert preview == {
        "provider": "xai",
        "method": "POST",
        "url": "https://api.x.ai/v1/images/generations",
        "headers": {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer <redacted>",
        },
        "body": {
            "model": "grok-imagine-image-2.0",
            "prompt": rendered["prompt"],
            "n": 2,
            "aspect_ratio": "2:3",
            "response_format": "b64_json",
            "resolution": "2k",
        },
        "unsupported": {
            "negative_prompt": "xAI image generation does not accept negative_prompt",
            "seed": "xAI image generation does not accept seed",
            "quality": "xAI image generation does not accept quality",
        },
    }
    assert preview["body"]["prompt"] == rendered["prompt"]
    assert rendered["negative_prompt"] not in preview["body"]["prompt"]
    assert "must-never-appear" not in output


def test_dry_run_prompt_too_long_is_one_error_line_without_traceback(
    monkeypatch, capsys
):
    path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "recipes/integration/23-aspect-unlisted.json"
    )
    assert _main(monkeypatch, "--dry-run", "--recipe", path) == 1

    # Derived, not hardcoded: the message must report the length this recipe
    # actually renders to, so an edit to any template cannot make the error
    # quietly stale. A literal here breaks on every prompt change instead.
    from lith import load_recipe, render_prompt

    expected = len(render_prompt(load_recipe(path))["prompt"])
    assert expected > 1500, "this recipe must exceed MiniMax's cap to be a fixture"

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Traceback" not in captured.err

    lines = captured.err.splitlines()
    # The failure is the last line and stands alone. Anything before it is an
    # advisory warning — this recipe asks 4:5, which MiniMax clamps to 3:4 —
    # and every one of those must be prefixed so the error stays unambiguous.
    assert lines[-1] == (
        f"MiniMax prompt length is {expected} characters; cap is 1500. See "
        "backlog §3.1: lith testbed prompts require compact templates before "
        "MiniMax can render them"
    )
    assert all(line.startswith("warning: ") for line in lines[:-1])
    assert any("cannot produce 4:5" in line for line in lines[:-1])


def test_auth_reports_every_provider_tier_source_and_fingerprint_without_secrets(
    tmp_path, monkeypatch, capsys
):
    root, path = _recipe(tmp_path)
    secrets = {
        "XAI_API_KEY": "xai-secret",
        "OPENAI_API_KEY": "openai-secret",
        "MINIMAX_API_KEY": "minimax-secret",
    }
    (root / ".env").write_text("".join(f"{key}={value}\n" for key, value in secrets.items()))

    assert _main(monkeypatch, "--recipe", path, "--auth") == 0
    output = capsys.readouterr().out
    for provider in ("xai", "openai", "minimax"):
        line = next(line for line in output.splitlines() if line.startswith(f"{provider}:"))
        assert "tier 2" in line
        assert str(root / ".env") in line
        assert re.search(r"fingerprint [0-9a-f]{8}$", line)
    for secret in secrets.values():
        assert secret not in output


def test_auth_reports_missing_providers_and_does_not_read_real_hermes(
    tmp_path, monkeypatch, capsys
):
    _, path = _recipe(tmp_path)
    assert _main(monkeypatch, "--recipe", path, "--auth") == 0
    output = capsys.readouterr().out
    assert "xai: missing" in output
    assert "openai: missing" in output
    assert "minimax: missing" in output
    assert "tier 4 ~/.hermes/auth.json" in output


def test_hermes_model_parser_is_nested_quoted_and_config_precedes_env(tmp_path):
    home = tmp_path / "hermes-home"
    hermes = home / ".hermes"
    hermes.mkdir(parents=True)
    (hermes / "config.yaml").write_text(
        "other:\n"
        "  model: wrong-model\n"
        "image_gen:\n"
        "  provider: xai\n"
        "  model: 'grok-imagine-image-2.0' # active\n"
    )
    assert call_cli.hermes_active_model(
        home=home, environ={"FAL_IMAGE_MODEL": "fallback-model"}
    ) == ("grok-imagine-image-2.0", "~/.hermes/config.yaml:image_gen.model")


def test_hermes_model_parser_falls_back_to_fal_image_model(tmp_path):
    assert call_cli.hermes_active_model(
        home=tmp_path, environ={"FAL_IMAGE_MODEL": "fal-ai/flux"}
    ) == ("fal-ai/flux", "FAL_IMAGE_MODEL")
    assert call_cli.hermes_active_model(home=tmp_path, environ={}) == (
        None,
        "not configured",
    )


@pytest.mark.parametrize(
    ("active", "aspect", "route", "reason_parts"),
    [
        ("grok-imagine-image-2.0", "16:9", "image_generate", ("matches", "16:9")),
        ("grok-imagine-image-2.0", "2:3", "lith-call", ("cannot preserve", "2:3")),
        ("another-model", "16:9", "lith-call", ("does not match",)),
        ("another-model", "2:3", "lith-call", ("does not match", "cannot preserve")),
    ],
)
def test_routing_requires_both_model_and_exact_aspect(
    tmp_path, active, aspect, route, reason_parts
):
    decision = call_cli.routing_decision(
        "grok-imagine-image-2.0",
        aspect,
        home=tmp_path,
        environ={"FAL_IMAGE_MODEL": active},
    )
    assert decision["route"] == route
    for part in reason_parts:
        assert part in decision["reason"]


def test_check_prints_route_and_specific_reason_without_auth(
    tmp_path, monkeypatch, capsys
):
    _, path = _recipe(tmp_path, aspect="2:3")
    monkeypatch.setenv("FAL_IMAGE_MODEL", "grok-imagine-image-2.0")

    def forbidden(*args, **kwargs):
        raise AssertionError("--check must not resolve credentials or call a provider")

    monkeypatch.setattr(call_cli, "resolve_credential", forbidden)
    monkeypatch.setattr(call_cli, "generate", forbidden)
    assert _main(monkeypatch, "--recipe", path, "--check") == 0
    output = capsys.readouterr().out
    assert "route=lith-call" in output
    assert "reason=Hermes image_generate cannot preserve resolved aspect '2:3'" in output


def test_previous_grok_live_recipe_is_capable_and_routable(tmp_path):
    path = pathlib.Path(__file__).resolve().parents[1] / "recipes" / "live_test_recipe.json"
    recipe = load_recipe(path)
    rendered = render_prompt(recipe)

    assert recipe.model == "grok-imagine-image-quality"
    assert provider_for_model(recipe.model) == "xai"
    assert rendered["aspect_note"] is None
    assert call_cli.routing_decision(
        recipe.model,
        rendered["aspect_ratio"],
        home=tmp_path,
        environ={"FAL_IMAGE_MODEL": recipe.model},
    )["route"] == "image_generate"
    assert request_preview(
        ImageRequest(
            prompt=rendered["prompt"],
            model=recipe.model,
            aspect=rendered["aspect_ratio"],
            negative_prompt=rendered["negative_prompt"],
        )
    )["provider"] == "xai"


def test_live_call_is_recipe_anchored_preserves_prompt_and_writes_magic_extensions(
    tmp_path, monkeypatch, capsys
):
    _, path = _recipe(tmp_path)
    out = tmp_path / "chosen"
    credential = Credential("xai", "fixture-secret", 1, "fixture", "api_key")
    result = CallResult(
        candidates=[
            Candidate(0, _png(), "reported/wrong", (20, 30)),
            Candidate(1, b"\xff\xd8\xfffixture", "reported/wrong", None),
        ],
        model_reported="grok-imagine-image-2.0",
        aspect_reported="2:3",
        revised_prompt="",
        unsupported={"negative_prompt": "not accepted"},
        cost="17",
        raw={"usage": {"cost_in_usd_ticks": 17}},
    )
    calls = {}

    def resolve(provider, **kwargs):
        calls["resolve"] = (provider, kwargs)
        return credential

    def generate(request, **kwargs):
        calls["generate"] = (request, kwargs)
        return result

    monkeypatch.setattr(call_cli, "resolve_credential", resolve)
    monkeypatch.setattr(call_cli, "generate", generate)
    assert _main(
        monkeypatch,
        "--recipe", path,
        "--out", out,
        "--n", "2",
        "--resolution", "2k",
        "--seed", "11",
        "--emit-json",
    ) == 0

    metadata = json.loads(capsys.readouterr().out)
    assert calls["resolve"] == ("xai", {"recipe_path": path})
    request, kwargs = calls["generate"]
    assert kwargs == {"credential": credential}
    rendered = render_prompt(load_recipe(path))
    assert request.prompt == rendered["prompt"]
    assert request.negative_prompt == rendered["negative_prompt"]
    assert (request.n, request.resolution, request.seed) == (2, "2k", 11)
    expected = [out / "B_brutalist_ship-c0.png", out / "B_brutalist_ship-c1.jpg"]
    assert [pathlib.Path(item["path"]) for item in metadata["candidates"]] == expected
    assert expected[0].read_bytes() == result.candidates[0].data
    assert expected[1].read_bytes() == result.candidates[1].data
    assert metadata["unsupported"] == {"negative_prompt": "not accepted"}
    assert metadata["raw"] == result.raw


def test_invalid_candidate_prevents_the_entire_batch_from_being_written(tmp_path):
    result = CallResult(
        [
            Candidate(0, _png(), "image/png", (20, 30)),
            Candidate(1, b"not-image", "image/png", None),
        ],
        None,
        None,
        None,
        {},
        None,
        {},
    )
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="candidate 1"):
        call_cli._write_candidates(
            result, output_dir=out, family_key="B_brutalist", headline="SHIP"
        )
    assert not out.exists()


def test_pyproject_registers_lith_call_without_runtime_dependencies():
    pyproject = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text()
    assert 'lith-call = "lith.cli.call:main"' in text
    project_section = text.split("[project]", 1)[1].split("[project.optional-dependencies]", 1)[0]
    assert "dependencies" not in project_section


BED = pathlib.Path(__file__).resolve().parents[1] / "recipes" / "integration"


@pytest.mark.parametrize(
    "recipe,field,fragment",
    [
        ("22-aspect-clamped", "aspect_note", "cannot produce 16:9"),
        ("20-aspect-family", "copy_note", "letter template wording"),
    ],
)
def test_check_surfaces_render_notes_on_both_channels(
    recipe, field, fragment, monkeypatch, capsys
):
    """lith-call must not swallow what lith-generate reports.

    A clamped ratio and a too-thin copy block are both substitutions the
    caller has to know about, and lith-call is the command that spends the
    money. It reported neither until this test existed: --emit-json omitted
    the field and stderr was zero bytes.
    """
    path = BED / f"{recipe}.json"
    assert _main(monkeypatch, "--check", "--recipe", path, "--emit-json") == 0

    captured = capsys.readouterr()
    assert fragment in captured.err, "note missing from stderr"
    assert captured.err.startswith("warning: ")
    payload = json.loads(captured.out)
    assert fragment in payload[field], "note missing from --emit-json"


def test_dry_run_carries_render_notes_too(monkeypatch, capsys):
    path = BED / "22-aspect-clamped.json"
    assert _main(monkeypatch, "--dry-run", "--recipe", path, "--emit-json") == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "cannot produce 16:9" in payload["aspect_note"]
    # The plan a caller inspects must show the substituted size, not 16:9.
    assert payload["body"]["size"] == "1536x1024"


def test_render_notes_drops_empty_values():
    from lith.cli.call import render_notes

    assert render_notes({"aspect_note": None, "copy_note": "", "limit_notes": []}) == {}
    assert render_notes({"aspect_note": "x"}) == {"aspect_note": "x"}
