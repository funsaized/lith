import sys

import pytest

from lith import expand_brief, parse_brief_response


def test_parse_fenced_json():
    text = """Here's the brief:
```json
{"topic": "...", "headline": "32 LANGS", "icon": "globe", "aspect": "16:9"}
```
Hope that helps!"""
    out = parse_brief_response(text)
    assert out["headline"] == "32 LANGS"
    assert out["aspect"] == "16:9"


def test_parse_unfenced_json():
    text = """Sure, here's a brief for that topic:

{"topic": "...", "headline": "32 LANGS", "icon": "globe", "aspect": "16:9"}

Let me know if you want changes."""
    out = parse_brief_response(text)
    assert out["headline"] == "32 LANGS"
    assert out["aspect"] == "16:9"


def test_parse_nested_json_picks_outer_object():
    text = """Brief:

{"headline": "X", "palette": {"accent": "#fff"}, "aspect": "16:9"}

Done."""
    out = parse_brief_response(text)
    assert out["headline"] == "X"
    assert out["aspect"] == "16:9"
    assert "palette" in out


def test_parse_prose_with_braces_then_real_object():
    text = """Pick from {gear, lightning, globe} based on the topic.

{"topic": "t", "headline": "X", "icon": "globe", "aspect": "16:9"}"""
    out = parse_brief_response(text)
    assert out["headline"] == "X"
    assert out["icon"] == "globe"


def test_parse_garbage_raises():
    with pytest.raises(ValueError, match="could not extract JSON"):
        parse_brief_response("Sorry, I can't help with that.")


def test_expand_brief_survives_braces_in_default_prompt():
    stub_cmd = [
        sys.executable,
        "-c",
        "import sys; sys.stdin.read(); "
        "print('{\"topic\":\"t\",\"headline\":\"X\",\"icon\":\"globe\",\"aspect\":\"16:9\"}')",
    ]
    out = expand_brief("test topic", llm_cmd=stub_cmd)
    assert out["headline"] == "X"
    assert out["icon"] == "globe"
