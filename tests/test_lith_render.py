import json

import pytest

from lith import load_recipe, output_path, render_prompt, slug
from lith.recipe import FAMILY_KEYS
from lith.styles import get_family, load_styles


def test_slug_lowercases_and_strips_non_alnum():
    assert slug("32 LANGS") == "32_langs"
    assert slug("AI/ML: v2") == "ai_ml_v2"
    assert slug("  ") == "untitled"


def test_output_path_uses_slug(tmp_path):
    p = output_path(tmp_path, "B_brutalist", "32 LANGS", ".png")
    assert p == tmp_path / "B_brutalist_32_langs.png"


def test_load_recipe_validates_required_fields(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(
        json.dumps(
            {
                "name": "x",
                "style": "B",
                "brief": {
                    "topic": "t",
                    "headline": "h",
                    "icon": "i",
                    "aspect": "16:9",
                },
                "model": "grok-imagine-image-quality",
            }
        )
    )
    r = load_recipe(str(p))
    assert r.name == "x"
    assert r.family_key == "B_brutalist"
    assert render_prompt(r)["style"] == "Sci-fi brutalist UI"


def test_load_recipe_rejects_missing_brief_fields(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"name": "x", "style": "B", "brief": {"topic": "t"}}))
    with pytest.raises(ValueError, match="missing brief fields"):
        load_recipe(p)


def test_render_prompt_substitutes_fields():
    style = {
        "prompt_template": "Headline={headline} icon={icon} bg={base_color} accent={accent}",
        "negative_prompt": "pastel",
        "palette": {"accent": "#00E5FF", "background": "#000000"},
        "name": "Test", "default_aspect": "16:9",
    }
    out = render_prompt(style, {"headline": "32 LANGS", "icon": "globe", "aspect": "16:9"})
    assert out["prompt"].startswith("Headline=32 LANGS")
    assert "bg=#000000" in out["prompt"]
    assert out["aspect_ratio"] == "16:9"


def test_palette_value_joins_lists_with_pipe():
    """A_sticker's list of accents must preserve the original join behavior."""
    style = {
        "prompt_template": "palette: {accent}",
        "palette": {"accent": ["#FF2E88", "#00E5FF", "#F2FF00", "#FF6B35"]},
        "name": "X", "default_aspect": "16:9",
    }
    out = render_prompt(style, {"headline": "X", "icon": "i", "aspect": "16:9"})
    assert "FF2E88 | #00E5FF | #F2FF00 | #FF6B35" in out["prompt"]


def test_all_seven_families_have_headline_slot():
    """Every family template must include the rendered headline."""
    styles = load_styles()
    for letter in "ABCDEFG":
        fam = get_family(styles, letter)
        out = render_prompt(
            fam,
            {
                "topic": "t",
                "headline": "TEST_HEADLINE",
                "icon": "gear",
                "aspect": "16:9",
            },
        )
        assert "{headline}" not in out["prompt"], (
            f"family {letter} left an unfilled {{headline}} placeholder: {out['prompt'][:200]}"
        )
        assert "TEST_HEADLINE" in out["prompt"], (
            f"family {letter} dropped the headline from the rendered prompt"
        )


def test_family_keys_complete():
    for letter in "ABCDEFG":
        assert letter in FAMILY_KEYS
    assert FAMILY_KEYS["B"] == "B_brutalist"
