from dataclasses import asdict
import json
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

import pytest

from lith import load_recipe, recipe_from_brief
from lith.cli import print as publish
from lith.svg import render_svg


NS = {"s": "http://www.w3.org/2000/svg"}


def recipe(**changes):
    brief = dict(topic="copy", headline="SHIP", icon="none", aspect="1:1")
    brief.update(changes)
    return recipe_from_brief(brief, style="B", n=1)


def copy_values(data):
    return {node.attrib["data-copy"]: "".join(node.itertext())
            for node in ET.fromstring(data).findall("s:text", NS)}


def test_exact_copy_escaping_wrapping_order_repetitions_and_title_override():
    authored = recipe(
        title='A <script> & "quoted" title', subtitle="  preserved   spaces  ",
        sections=[{"heading": "SAME", "lines": ["word " * 35, "X" * 130]},
                  {"heading": "SAME", "lines": ["Repeated", "Repeated"]}], footer="END.",
        aspect="2:3",
    )
    before = json.dumps(asdict(authored))
    data = render_svg(authored)
    assert data == render_svg(authored)
    assert json.dumps(asdict(authored)) == before
    expected = {
        "title": authored.brief["title"], "subtitle": authored.brief["subtitle"],
        "sections/0/heading": "SAME", "sections/0/lines/0": "word " * 35,
        "sections/0/lines/1": "X" * 130, "sections/1/heading": "SAME",
        "sections/1/lines/0": "Repeated", "sections/1/lines/1": "Repeated", "footer": "END.",
    }
    assert copy_values(data) == expected
    root = ET.fromstring(data)
    assert [node.attrib["data-copy"] for node in root.findall("s:text", NS)] == list(expected)
    assert not root.findall(".//s:script", NS)
    assert not root.findall(".//s:image", NS)
    assert b"&lt;script&gt;" in data
    assert b"SHIP" not in data


@pytest.mark.parametrize("aspect,size", [("1:1", (1200, 1200)), ("2:3", (1200, 1800)), ("3:2", (1200, 800))])
def test_example_copy_and_advance_boxes_fit_each_supported_frame(aspect, size):
    authored = load_recipe(Path(__file__).parents[1] / "recipes/deterministic.json")
    authored.brief["aspect"] = aspect
    root = ET.fromstring(render_svg(authored))
    assert (int(root.attrib["width"]), int(root.attrib["height"])) == size
    for span in root.findall(".//s:tspan", NS):
        assert float(span.attrib["x"]) + float(span.attrib["textLength"]) <= size[0] - 48
        assert 0 < float(span.attrib["y"]) < size[1] - 40


def test_auto_aspect_and_model_independence():
    authored = recipe(aspect="auto")
    first = render_svg(authored)
    assert ET.fromstring(first).attrib["height"] == "1200"
    authored.model = "image-01"
    authored.n = 3
    assert render_svg(authored) == first
    authored.brief.pop("aspect")
    authored.brief["sections"] = [{"heading": "H"}] * 3
    assert ET.fromstring(render_svg(authored)).attrib["height"] == "1800"


@pytest.mark.parametrize("changes,match", [
    ({"diagram": "Draw labels A and B"}, "diagram"),
    ({"diagram_position": "above"}, "diagram_position"),
    ({"layout": "grid"}, "layout"),
    ({"accent": "red"}, "accent"),
    ({"aspect": "16:9"}, "aspects"),
    ({"prompt_mode": "compact"}, "standard"),
    ({"headline": "café"}, "ASCII"),
    ({"headline": "a\nb"}, "ASCII"),
    ({"headline": "a\tb"}, "ASCII"),
    ({"sections": [{"heading": "H", "caption": "keep this"}]}, "only heading"),
    ({"headline": "LONG " * 1000}, "nothing was published"),
])
def test_unsupported_content_fails_instead_of_changing_copy(changes, match):
    with pytest.raises(ValueError, match=match):
        render_svg(recipe(**changes))


def test_other_families_rejected():
    authored = recipe()
    authored.style = "A"
    with pytest.raises(ValueError, match="family B"):
        render_svg(authored)


def test_cli_is_offline_and_failed_render_preserves_previous_output(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("SVG rendering must not invoke image or prompt generation")
    monkeypatch.setattr(publish, "fetch_image", forbidden)
    monkeypatch.setattr(publish, "render_prompt", forbidden)
    path = tmp_path / "recipe.json"
    authored = recipe()
    path.write_text(json.dumps(asdict(authored)))
    out = tmp_path / "out"
    args = ["lith-print", "--recipe", str(path), "--svg", "--strict", "--output-dir", str(out)]
    monkeypatch.setattr(sys, "argv", args)
    assert publish.main() == 0
    published = out / "B_brutalist_ship.svg"
    previous = published.read_bytes()
    assert copy_values(previous) == {"headline": "SHIP"}
    with pytest.raises(ValueError, match="not a recognized image format"):
        publish._local_bytes(published)
    assert publish.main() == 0
    assert "overwriting" in capsys.readouterr().out
    authored.brief["footer"] = "too much copy " * 1000
    path.write_text(json.dumps(asdict(authored)))
    with pytest.raises(SystemExit) as error:
        publish.main()
    assert error.value.code == 2
    assert published.read_bytes() == previous
    monkeypatch.setattr(sys, "argv", args + ["--image-url", "https://example.com/image.png"])
    with pytest.raises(SystemExit):
        publish.main()
