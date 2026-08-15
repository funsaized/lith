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


def test_format_spec_serializes_sections():
    from lith.render import format_spec

    out = format_spec(
        {
            "headline": "TAILSCALE",
            "subtitle": "THREE MACHINES",
            "sections": [{"heading": "01 - THE HUB", "lines": ["Mac mini M4", "always on"]}],
            "diagram": "cloud over three boxes",
            "footer": "s11a.com",
        }
    )
    assert "TITLE: TAILSCALE" in out
    assert "SECTION 1 HEADING: 01 - THE HUB" in out
    assert "    - Mac mini M4" in out
    assert "DIAGRAM: cloud over three boxes" in out
    assert "FOOTER: s11a.com" in out


def test_format_spec_degrades_to_headline_for_legacy_briefs():
    from lith.render import format_spec

    assert format_spec({"headline": "32 LANGS", "icon": "globe"}) == "TITLE: 32 LANGS"


def test_spec_copy_reaches_the_rendered_prompt():
    """Section body lines must survive into the prompt verbatim."""
    styles = load_styles()
    out = render_prompt(
        get_family(styles, "D"),
        {
            "topic": "t",
            "headline": "TAILSCALE",
            "icon": "lightning",
            "aspect": "4:5",
            "sections": [{"heading": "02 - THE MESH", "lines": ["No open ports"]}],
        },
    )
    assert "02 - THE MESH" in out["prompt"]
    assert "No open ports" in out["prompt"]
    assert "{spec}" not in out["prompt"]


def test_brief_base_color_overrides_palette_list():
    """A family with several palette backgrounds must let the recipe pick one."""
    styles = load_styles()
    brief = {"topic": "t", "headline": "X", "icon": "gear", "aspect": "4:5"}
    without = render_prompt(get_family(styles, "D"), brief)["prompt"]
    with_pick = render_prompt(get_family(styles, "D"), {**brief, "base_color": "#FFD700"})["prompt"]
    assert "#FFD700 | #FF2E88" in without
    assert "background (#FFD700)" in with_pick


def test_layout_zones_track_the_spec():
    """A zone is described only when the brief has copy for it."""
    from lith.render import format_layout

    base = {"headline": "SHIP"}
    sparse = format_layout(base)
    assert "SECTION PANELS" not in sparse
    assert "DIAGRAM" not in sparse
    assert "FOOTER" not in sparse
    assert "dominating the composition" in sparse  # title carries a bare poster

    full = format_layout(
        {**base, "subtitle": "S", "footer": "f", "diagram": "d",
         "sections": [{"heading": "A", "lines": ["x"]}, {"heading": "B", "lines": ["y"]}]}
    )
    assert "2 SECTION PANELS" in full
    assert "DIAGRAM PANEL" in full
    assert "FOOTER" in full
    assert "12-15%" in full  # title yields to the body copy


def test_layout_columns_follow_section_count():
    from lith.render import format_layout

    def cols(n):
        b = {"headline": "X", "sections": [{"heading": str(i), "lines": ["l"]} for i in range(n)]}
        return format_layout(b)

    assert "a single column" in cols(2)
    assert "two columns" in cols(4)


def test_section_without_heading_raises_a_useful_error():
    from lith.render import format_spec

    with pytest.raises(ValueError, match="section 1 has no 'heading'"):
        format_spec({"headline": "X", "sections": [{"lines": ["orphan"]}]})


def test_default_output_dir_anchors_to_the_recipe_not_cwd(tmp_path):
    from lith.paths import default_output_dir

    # Repo layout: recipes/x.json publishes to the sibling outputs/.
    nested = tmp_path / "recipes" / "x.json"
    nested.parent.mkdir(parents=True)
    nested.write_text("{}")
    assert default_output_dir(nested) == tmp_path / "outputs"

    # Anywhere else: publish beside the recipe.
    flat = tmp_path / "loose.json"
    flat.write_text("{}")
    assert default_output_dir(flat) == tmp_path / "outputs"


def test_unsupported_aspect_names_what_the_model_can_do():
    from lith.aspect import unsupported_aspect

    # The defect this exists to prevent: grok has no 4:5 and substitutes silently.
    msg = unsupported_aspect("grok-imagine-image-quality", "4:5")
    assert msg and "cannot produce 4:5" in msg

    # gpt-image-1 is narrower still — 16:9 is fine on grok, not on OpenAI.
    assert unsupported_aspect("gpt-image-1", "16:9")
    assert unsupported_aspect("grok-imagine-image-quality", "16:9") is None

    # 2:3 is the portrait ratio both can produce; every family default must pass.
    assert unsupported_aspect("gpt-image-1", "2:3") is None
    assert unsupported_aspect("grok-imagine-image-quality", "2:3") is None

    # An unknown model is unconstrained rather than wrongly flagged.
    assert unsupported_aspect("some-future-model", "4:5") is None


def test_every_family_default_aspect_is_producible():
    """A family must not default to a ratio its own default model cannot make."""
    from lith.aspect import unsupported_aspect

    styles = load_styles()
    for letter in "ABCDEFG":
        aspect = get_family(styles, letter)["default_aspect"]
        bad = unsupported_aspect("grok-imagine-image-quality", aspect)
        assert bad is None, f"family {letter}: {bad}"


def test_resolve_aspect_precedence():
    """Explicit beats content shape beats family default — then the model clamps."""
    from lith.aspect import resolve_aspect

    spec_style = {"prompt_template": "{spec}{layout}", "default_aspect": "16:9"}
    plain_style = {"prompt_template": "{headline}", "default_aspect": "16:9"}
    dense = [{"heading": str(i), "lines": ["x"]} for i in range(4)]

    # 1. explicit wins over everything below it
    assert resolve_aspect({"aspect": "1:1", "sections": dense}, spec_style)[0] == "1:1"
    # 2. content shape: 3+ panels need vertical room
    assert resolve_aspect({"sections": dense}, spec_style)[0] == "2:3"
    assert resolve_aspect({"sections": dense[:2]}, spec_style)[0] == "1:1"
    # 3. content shape is ignored by families that do not render a spec
    assert resolve_aspect({"sections": dense}, plain_style)[0] == "16:9"
    # 4. family default when the brief says nothing
    assert resolve_aspect({}, spec_style)[0] == "16:9"


def test_resolve_aspect_clamps_to_what_the_model_can_make():
    from lith.aspect import resolve_aspect

    style = {"prompt_template": "{headline}", "default_aspect": "16:9"}
    aspect, note = resolve_aspect({}, style, "gpt-image-1")
    assert aspect == "3:2", "16:9 must land on the nearest landscape gpt-image-1 has"
    assert note and "nearest supported 3:2" in note

    # A portrait request must not be clamped onto a landscape ratio.
    aspect, _ = resolve_aspect({"aspect": "9:16"}, style, "gpt-image-1")
    assert aspect == "2:3"

    # Supported requests pass through silently; unknown models are unconstrained.
    assert resolve_aspect({"aspect": "2:3"}, style, "gpt-image-1") == ("2:3", None)
    assert resolve_aspect({"aspect": "4:5"}, style, "who-knows") == ("4:5", None)


def test_render_prompt_takes_the_model_from_a_recipe(tmp_path):
    """A Recipe already names its model, so clamping needs no extra argument."""
    import json

    p = tmp_path / "r.json"
    p.write_text(json.dumps({
        "style": "B", "model": "gpt-image-1",
        "brief": {"topic": "t", "headline": "h", "icon": "i", "aspect": "16:9"},
    }))
    out = render_prompt(load_recipe(p))
    assert out["aspect_ratio"] == "3:2"
    assert out["aspect_note"]


def test_every_family_carries_the_spec_and_layout_slots():
    """The spec model is the single copy path — no family may opt out."""
    styles = load_styles()
    for letter in "ABCDEFG":
        template = get_family(styles, letter)["prompt_template"]
        assert "{spec}" in template, f"family {letter} has no {{spec}} slot"
        assert "{layout}" in template, f"family {letter} has no {{layout}} slot"
        assert "EXACTLY as written" in template, f"family {letter} lost the verbatim order"


def test_every_family_renders_a_dense_spec_intact():
    """Section headings and body lines must survive into all seven prompts."""
    styles = load_styles()
    brief = {
        "topic": "t", "headline": "SHIP", "icon": "gear", "volume": "1",
        "subtitle": "SUBTITLE HERE",
        "sections": [
            {"heading": "01 - ALPHA", "lines": ["first body line", "second body line"]},
            {"heading": "02 - BETA", "lines": ["third body line"]},
        ],
        "diagram": "a box labeled ALPHA wired to a box labeled BETA",
        "footer": "example.com",
    }
    for letter in "ABCDEFG":
        out = render_prompt(get_family(styles, letter), brief)["prompt"]
        for needle in ("TITLE: SHIP", "SUBTITLE HERE", "01 - ALPHA", "02 - BETA",
                       "first body line", "third body line",
                       "wired to a box labeled BETA", "FOOTER: example.com"):
            assert needle in out, f"family {letter} dropped {needle!r}"
        assert "2 SECTION PANELS" in out, f"family {letter} lost its panel zone"
        for slot in ("{spec}", "{layout}", "{headline}", "{icon}", "{volume}",
                     "{base_color}", "{accent}"):
            assert slot not in out, f"family {letter} left {slot} unfilled"


def test_every_family_still_handles_a_sparse_brief():
    """A title-only brief must not order panels no copy exists for."""
    styles = load_styles()
    for letter in "ABCDEFG":
        out = render_prompt(
            get_family(styles, letter),
            {"topic": "t", "headline": "SHIP", "icon": "gear", "volume": "1"},
        )["prompt"]
        assert "SECTION PANELS" not in out, f"family {letter} orders empty panels"
        assert "dominating the composition" in out, f"family {letter} lost title scaling"
        assert "TITLE: SHIP" in out
