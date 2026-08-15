import json
import subprocess

DEFAULT_PROMPT = """You are a brief-expander for a tech-image generator.

Given a topic, produce a JSON object with these fields:
- topic: one-sentence summary
- headline: 1-3 words, ALL CAPS, suitable for overlay
- icon: motif from {gear, lightning, globe, skull, brain, rocket, lock}
- aspect: 16:9, 4:5, 1:1, or 9:16
- mood: 1-2 word feel descriptor

Pick icon and aspect based on the topic. Use the style B (Sci-fi brutalist UI)
default unless the topic calls for something else.

Respond with ONLY a JSON code block. No prose outside the block.

Topic: {topic}
"""


def parse_brief_response(text: str) -> dict:
    """Find the first valid JSON object in an LLM response."""
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text, index)
            return obj
        except json.JSONDecodeError:
            continue
    raise ValueError(f"could not extract JSON from LLM response: {text[:200]!r}")


def expand_brief(
    topic: str,
    llm_cmd: list[str],
    prompt_template: str = DEFAULT_PROMPT,
    timeout: int = 60,
) -> dict:
    """Ask an LLM CLI to expand a topic into a structured brief."""
    # ``str.format`` cannot be used because the prose contains a brace list.
    prompt = prompt_template.replace("{topic}", topic)
    result = subprocess.run(
        llm_cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return parse_brief_response(result.stdout)
