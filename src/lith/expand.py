import json
import subprocess

DEFAULT_PROMPT = """You are a brief-expander for a dense technical poster generator.

Given a topic, produce a JSON object with these fields:
- topic: one-sentence summary
- headline: the poster title, 1-3 words, ALL CAPS
- subtitle: one line, ALL CAPS, under 8 words
- sections: 3-5 objects, each {heading, lines}. heading is 2-4 words ALL CAPS,
  optionally numbered like "01 - THE HUB". lines is 2-4 strings, each under 9
  words, concrete and specific — real names, numbers, commands — never filler.
- diagram: one sentence describing a simple labeled diagram, naming every label
- footer: one short line (site, handle, or date)
- icon: motif from {gear, lightning, globe, skull, brain, rocket, lock}
- aspect: 2:3, 3:2, or 1:1 — prefer 2:3 once there are 4+ sections

Every word you write is printed verbatim into the image, so write only text you
want to see rendered. Keep total body copy across all sections to 60-140 words.

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
