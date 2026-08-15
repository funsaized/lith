"""The integration testbed, checked without calling a model.

Every recipe under recipes/integration/ must load, render, and satisfy the
invariants the pipeline promises. This is what makes the testbed self-checking:
a live sweep costs money, but the prompt-side contract can be verified free.
"""

import json
import pathlib
import re

import pytest

from lith import load_recipe, output_path, render_prompt
from lith.aspect import MODEL_ASPECTS, ratio
from lith.layout import ARRANGEMENTS, DIAGRAM_POSITIONS
from lith.styles import get_family, load_styles

BED = pathlib.Path(__file__).resolve().parents[1] / "recipes" / "integration"
RECIPES = sorted(BED.glob("*.json"))
SLOTS = ("{spec}", "{layout}", "{headline}", "{icon}", "{volume}",
         "{base_color}", "{accent}")
# Strings that must never reach the prompt as something a model could letter.
LEAKS = ("TITLE BLOCK", "SECTION PANELS", "DIAGRAM PANEL", "DIAGRAM:", "FOOTER —")


def test_testbed_is_present():
    assert len(RECIPES) >= 30, f"expected a populated testbed, found {len(RECIPES)}"


@pytest.mark.parametrize("path", RECIPES, ids=lambda p: p.stem)
def test_recipe_renders_cleanly(path):
    rendered = render_prompt(load_recipe(path))
    prompt = rendered["prompt"]

    for slot in SLOTS:
        assert slot not in prompt, f"unfilled {slot}"
    for leak in LEAKS:
        assert leak not in prompt, f"letterable zone label {leak!r}"

    assert "never letter any instruction from above" in prompt
    assert ratio(rendered["aspect_ratio"]) is not None

    brief = json.loads(path.read_text())["brief"]
    # Every authored word must survive into the copy block.
    for section in brief.get("sections", []):
        assert section["heading"] in prompt
        for line in section["lines"]:
            assert line in prompt
    for key in ("subtitle", "footer"):
        if brief.get(key):
            assert brief[key] in prompt
    # A diagram is described, never quoted into the literal copy block.
    if brief.get("diagram"):
        assert brief["diagram"] in prompt
        assert f"DIAGRAM: {brief['diagram']}" not in prompt


@pytest.mark.parametrize("path", RECIPES, ids=lambda p: p.stem)
def test_recipe_aspect_is_producible(path):
    """Whatever the chain resolves must be something the model can make."""
    recipe = load_recipe(path)
    aspect = render_prompt(recipe)["aspect_ratio"]
    supported = MODEL_ASPECTS.get(recipe.model)
    if supported is not None:
        assert aspect in supported, f"{recipe.model} cannot produce {aspect}"


def _briefs():
    return [json.loads(p.read_text())["brief"] for p in RECIPES]


def test_testbed_covers_every_layout():
    used = {b["layout"] for b in _briefs() if "layout" in b}
    missing = set(ARRANGEMENTS) - used
    assert not missing, f"layouts never exercised: {sorted(missing)}"


def test_testbed_covers_every_diagram_position():
    used = set()
    for b in _briefs():
        if not b.get("diagram"):
            continue
        used.add(b.get("diagram_position") or
                 ("center" if b.get("layout") == "radial" else "below"))
    missing = set(DIAGRAM_POSITIONS) - used
    assert not missing, f"diagram positions never exercised: {sorted(missing)}"


def test_testbed_covers_every_family_and_model():
    docs = [json.loads(p.read_text()) for p in RECIPES]
    families = {d["style"] for d in docs}
    assert families == set("ABCDEFG"), f"families missing: {set('ABCDEFG') - families}"
    models = {d["model"] for d in docs}
    assert set(MODEL_ASPECTS) <= models, f"models missing: {set(MODEL_ASPECTS) - models}"
    assert "minimax-image" in models, "an unlisted model must be exercised too"


def test_testbed_covers_every_aspect_resolution_rung():
    briefs = _briefs()
    assert any("aspect" in b for b in briefs), "no explicit aspect"
    assert any("aspect" not in b and b.get("sections") for b in briefs), "no content-shape rung"
    assert any("aspect" not in b and not b.get("sections") for b in briefs), "no family-default rung"
    clamped = [p for p in RECIPES
               if render_prompt(load_recipe(p))["aspect_note"]]
    assert clamped, "no recipe exercises a model clamp"


def test_testbed_covers_sparse_and_dense_briefs():
    counts = {len(b.get("sections", [])) for b in _briefs()}
    assert 0 in counts, "no title-only brief"
    assert 1 in counts, "no single-section brief"
    assert max(counts) >= 6, "no dense brief"


# --- the same testbed driven through both console scripts -------------------
# Invoked in-process rather than by subprocess: same code path, and coverage
# instrumentation follows it.

def _main(module, argv, monkeypatch):
    import importlib
    import sys

    mod = importlib.import_module(module)
    monkeypatch.setattr(sys, "argv", [module, *argv])
    return mod.main()


@pytest.mark.parametrize("path", RECIPES, ids=lambda p: p.stem)
def test_generate_cli_emits_an_envelope(path, monkeypatch, capsys):
    rc = _main("lith.cli.generate",
               ["--recipe", str(path), "--call", "--emit-json"], monkeypatch)
    assert rc == 0
    envelope = json.loads(capsys.readouterr().out)
    assert set(envelope) == {
        "prompt", "negative_prompt", "aspect_ratio", "model", "n", "seed",
        "output_path", "style", "aspect_note", "copy_note",
    }
    assert envelope["model"] == json.loads(path.read_text())["model"]
    assert envelope["n"] == 2
    # A derived output path is a stem; the extension follows the bytes.
    assert not pathlib.Path(envelope["output_path"]).suffix


@pytest.mark.parametrize("path", RECIPES, ids=lambda p: p.stem)
def test_run_cli_dry_runs(path, monkeypatch, capsys, tmp_path):
    rc = _main("lith.cli.run",
               ["--recipe", str(path), "--output-dir", str(tmp_path)], monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    assert "[prompt]" in out and "Next:" in out
    assert not list(tmp_path.iterdir()), "a dry run must write nothing"


def test_run_cli_publishes_across_the_testbed(monkeypatch, tmp_path):
    """Publishing is format- and family-independent, so a sample suffices."""
    src = pathlib.Path(__file__).resolve().parents[1] / "outputs" / "B_brutalist_32_langs_raw.jpg"
    if not src.is_file():
        pytest.skip("reference artifact missing")
    for path in RECIPES[:6]:
        out = tmp_path / path.stem
        rc = _main("lith.cli.run",
                   ["--recipe", str(path), "--image-file", str(src),
                    "--output-dir", str(out)], monkeypatch)
        assert rc == 0
        published = list(out.glob("*.jpg"))
        assert len(published) == 1, f"{path.stem}: {list(out.iterdir())}"
        assert published[0].read_bytes() == src.read_bytes(), "must not re-encode"
        assert not list(out.glob("*.part")), "staging file left behind"


def test_generate_cli_warns_when_a_model_clamps(monkeypatch, capsys):
    clamping = [p for p in RECIPES
                if render_prompt(load_recipe(p))["aspect_note"]]
    assert clamping, "testbed must include a clamping row"
    _main("lith.cli.generate",
          ["--recipe", str(clamping[0]), "--call", "--emit-json"], monkeypatch)
    captured = capsys.readouterr()
    assert "warning:" in captured.err
    assert json.loads(captured.out)["aspect_note"]


# --- CLI surfaces a recipe cannot reach ------------------------------------

def test_generate_flag_mode_without_a_recipe(monkeypatch, capsys):
    rc = _main("lith.cli.generate",
               ["--topic", "t", "--style", "C", "--headline", "SHIP",
                "--icon", "gear", "--aspect", "4:3"], monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    assert "[brief]" in out and "[plan]" in out
    assert "TITLE: SHIP" in out


def test_generate_envelope_as_key_value_pairs(monkeypatch, capsys):
    rc = _main("lith.cli.generate",
               ["--topic", "t", "--style", "B", "--headline", "SHIP",
                "--call"], monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("prompt=")
    assert "aspect_ratio=" in out and "aspect_note=" in out


def test_generate_honours_explicit_out_and_seed(monkeypatch, capsys, tmp_path):
    target = tmp_path / "chosen.png"
    rc = _main("lith.cli.generate",
               ["--topic", "t", "--style", "G", "--headline", "SHIP",
                "--seed", "7", "--out", str(target), "--call", "--emit-json"],
               monkeypatch)
    assert rc == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["output_path"] == str(target)
    assert envelope["seed"] == 7


def test_generate_requires_the_flag_trio_without_a_recipe(monkeypatch):
    with pytest.raises(SystemExit) as excinfo:
        _main("lith.cli.generate", ["--topic", "t"], monkeypatch)
    assert excinfo.value.code == 2


def test_run_rejects_a_non_image_file(monkeypatch, tmp_path):
    junk = tmp_path / "not-an-image.jpg"
    junk.write_text("<html>rate limited</html>")
    with pytest.raises(ValueError, match="not a recognized image format"):
        _main("lith.cli.run",
              ["--recipe", str(RECIPES[0]), "--image-file", str(junk),
               "--output-dir", str(tmp_path)], monkeypatch)


def test_run_publishes_png_bytes_under_a_png_name(monkeypatch, tmp_path):
    """The extension follows the bytes, not the recipe or the source name."""
    src = tmp_path / "candidate.jpg"          # deliberately mislabelled
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 +
                    (1024).to_bytes(4, "big") + (1536).to_bytes(4, "big") + b"\x00" * 32)
    out = tmp_path / "published"
    rc = _main("lith.cli.run",
               ["--recipe", str(RECIPES[0]), "--image-file", str(src),
                "--output-dir", str(out)], monkeypatch)
    assert rc == 0
    assert len(list(out.glob("*.png"))) == 1
    assert not list(out.glob("*.jpg"))


# --- L1: contract checks that need no model call --------------------------
# Each of these locks a defect that a live sweep found only after paying for
# 68 generations, and that was visible in the rendered prompt all along.

# A quoted example of a *wrong* rendering is still text in the prompt. On a
# sparse brief the model lettered F_woodcut's counter-examples verbatim.
CONTENTISH = re.compile(r"\b\w+\.(?:com|dev|io|net|org)\b|\b[A-Z]{2,}-\d")


def test_no_style_template_carries_letterable_example_copy():
    for key, family in load_styles()["families"].items():
        text = family["prompt_template"]
        # Slots are filled from the brief; only the literal template is ours.
        literal = text.replace("{spec}", "").replace("{layout}", "")
        found = CONTENTISH.findall(literal)
        assert not found, (
            f"{key} embeds content-like literals {found}; a sparse brief will "
            "letter them as if they were spec copy"
        )


def test_sparse_briefs_are_flagged_and_dense_ones_are_not():
    from lith.render import copy_note

    sparse = {"topic": "t", "headline": "TAILSCALE", "icon": "lightning",
              "sections": []}
    note = render_prompt(get_family(load_styles(), "A"), sparse)["copy_note"]
    assert note and "letter template wording" in note

    for path in RECIPES:
        recipe = load_recipe(path)
        rendered = render_prompt(recipe)
        if recipe.brief.get("sections"):
            assert rendered["copy_note"] is None, (
                f"{path.stem} has sections but was flagged: {rendered['copy_note']}"
            )
        else:
            assert rendered["copy_note"], f"{path.stem} is empty but unflagged"

    # The ratio, not the raw length, is what matters: a long template needs
    # proportionally more copy to hold the model.
    assert copy_note("x" * 100, "x" * 100 + "i" * 2001).startswith("copy block is ")
    assert copy_note("x" * 100, "x" * 100 + "i" * 1999) is None


def test_testbed_output_stems_collide_so_a_sweep_must_isolate_them():
    """34 recipes share the headline TAILSCALE; they do not get 34 paths.

    This is `output_path` working as documented, not a bug — but a sweep that
    publishes them all into one directory keeps 7 files and loses 27, which is
    exactly what pushed an earlier harness into bypassing lith-run entirely.
    """
    stems = {
        output_path(pathlib.Path("/out"), load_recipe(p).family_key,
                    load_recipe(p).brief["headline"], "").name
        for p in RECIPES
    }
    assert len(stems) < len(RECIPES)
    assert len(stems) == 7, f"one stem per family expected, got {sorted(stems)}"
