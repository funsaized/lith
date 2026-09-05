"""Generated recipe integration: subprocess output through the CLI envelope."""

import json
import pathlib
import subprocess
import sys

import pytest

from lith import expand_brief, recipe_from_brief, render_prompt, validate_brief
from lith.cli import plate as plate_cli


FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "fake_brief_llm.py"
pytestmark = pytest.mark.integration


def _expand(mode: str, *, timeout: float = 2) -> dict:
    return expand_brief(
        "Dill Pickles and all the things that make them great",
        [sys.executable, str(FIXTURE), mode],
        timeout=timeout,
    )


def test_generated_brief_validates_renders_and_reaches_generate_envelope(
    tmp_path, monkeypatch, capsys
):
    brief = _expand("success")
    validate_brief(brief)
    recipe = recipe_from_brief(
        brief,
        style="B",
        model="grok-imagine-image-2.0",
        n=1,
        name="dill-pickle-generated",
    )
    rendered = render_prompt(recipe)
    assert '"DILL PICKLES"' in rendered["prompt"]
    assert "TITLE: DILL PICKLES" not in rendered["prompt"]
    assert "Fresh dill brings a grassy spark" in rendered["prompt"]

    path = tmp_path / "generated.json"
    path.write_text(
        json.dumps(
            {
                "name": recipe.name,
                "style": recipe.style,
                "model": recipe.model,
                "n": recipe.n,
                "brief": recipe.brief,
            }
        )
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["lith-plate", "--recipe", str(path), "--press", "--emit-json"],
    )
    assert plate_cli.main() == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["prompt"] == rendered["prompt"]
    assert envelope["model"] == recipe.model
    assert envelope["n"] == 1
    assert envelope["aspect_ratio"] == "2:3"


def test_generated_response_must_contain_json():
    with pytest.raises(ValueError, match="could not extract JSON"):
        _expand("malformed")


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("incomplete", "missing brief fields"),
        ("wrong-types", "brief.headline must be a non-empty string"),
        ("invalid-aspect", "brief.aspect must be"),
        ("malformed-sections", "section 1 has no 'heading'"),
    ],
)
def test_generated_json_is_validated_before_it_becomes_a_recipe(mode, message):
    brief = _expand(mode)
    with pytest.raises(ValueError, match=message):
        recipe_from_brief(brief, style="B")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"style": "Z"}, "style must be one of"),
        ({"model": "imaginary-image-model"}, "unknown model"),
    ],
)
def test_generated_recipe_rejects_invalid_routing_fields(overrides, message):
    kwargs = {"style": "B", **overrides}
    with pytest.raises(ValueError, match=message):
        recipe_from_brief(_expand("success"), **kwargs)


def test_generated_recipe_subprocess_timeout_is_preserved():
    with pytest.raises(subprocess.TimeoutExpired):
        _expand("timeout", timeout=0.01)


def test_generated_recipe_subprocess_failure_is_preserved():
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        _expand("failure")
    assert excinfo.value.returncode == 23


@pytest.mark.parametrize("aspect", ["nan:1", "1:nan", "inf:1", "1:inf", "-1:-2", "1e308:1e-308", "1e-308:1e308"])
def test_recipe_rejects_nonfinite_or_nonpositive_ratios(aspect):
    brief = {"topic": "test", "headline": "TEST", "icon": "gear", "aspect": aspect}
    with pytest.raises(ValueError, match="brief.aspect"):
        recipe_from_brief(brief, style="B")


@pytest.mark.parametrize("field", ["style", "model", "layout", "diagram_position"])
@pytest.mark.parametrize("value", [[], {}, 123])
def test_recipe_shape_errors_are_value_errors(field, value):
    brief = {"topic": "test", "headline": "TEST", "icon": "gear"}
    kwargs = {"style": "B"}
    if field in {"style", "model"}:
        kwargs[field] = value
    else:
        brief[field] = value
    with pytest.raises(ValueError, match=field):
        recipe_from_brief(brief, **kwargs)
