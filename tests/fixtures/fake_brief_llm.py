"""Deterministic subprocess fixture for the generated-recipe integration path."""

import json
import sys
import time


mode = sys.argv[1]
prompt = sys.stdin.read()

if mode == "timeout":
    time.sleep(5)
elif mode == "failure":
    print("simulated model failure", file=sys.stderr)
    raise SystemExit(23)
elif mode == "malformed":
    print("```json\n{this is not json}\n```")
else:
    brief = {
        "topic": "Why dill pickles make every sandwich brighter",
        "headline": "DILL PICKLES",
        "subtitle": "CRUNCH, TANG, AND BRINY JOY",
        "sections": [
            {
                "heading": "01 - THE CRUNCH",
                "lines": ["Cold cucumbers stay remarkably crisp", "Every bite wakes up lunch"],
            },
            {
                "heading": "02 - THE BRINE",
                "lines": ["Fresh dill brings a grassy spark", "Garlic and pepper add depth"],
            },
            {
                "heading": "03 - THE PAYOFF",
                "lines": ["Burgers gain a bright counterpoint", "Spears disappear straight from the jar"],
            },
        ],
        "diagram": "A pickle jar connects crunch, dill, garlic, and tang",
        "footer": "KEEP IT CRISP",
        "icon": "lightning",
        "aspect": "2:3",
    }
    if mode == "incomplete":
        brief.pop("icon")
    elif mode == "wrong-types":
        brief["headline"] = ["DILL", "PICKLES"]
    elif mode == "invalid-aspect":
        brief["aspect"] = "cinematic"
    elif mode == "malformed-sections":
        brief["sections"] = [{"lines": ["No heading here"]}]
    elif mode != "success":
        raise SystemExit(f"unknown fixture mode: {mode}")
    assert "Dill Pickles" in prompt
    print("Model preamble follows")
    print("```json")
    print(json.dumps(brief))
    print("```")
