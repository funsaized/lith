import json
import pathlib
from dataclasses import dataclass
from typing import Any

from .aspect import MODEL_ASPECTS, ratio
from .layout import ARRANGEMENTS, DIAGRAM_POSITIONS

FAMILY_KEYS = {
    "A": "A_sticker",
    "B": "B_brutalist",
    "C": "C_patent",
    "D": "D_manga",
    "E": "E_screenshot",
    "F": "F_woodcut",
    "G": "G_log",
}

# ``aspect`` is deliberately absent: it has a full resolution chain in
# lith.aspect (explicit -> content shape -> family default -> clamp), so
# requiring it in every recipe would make three of those rungs unreachable.
REQUIRED_BRIEF_KEYS = {"topic", "headline", "icon"}
TEXT_BRIEF_KEYS = {
    "topic", "headline", "title", "subtitle", "diagram", "footer", "icon",
    "volume",
}
DEFAULT_MODEL = "grok-imagine-image-2.0"



@dataclass
class Recipe:
    name: str
    style: str
    brief: dict
    model: str
    n: int
    description: str | None

    @property
    def family_key(self) -> str:
        return FAMILY_KEYS[self.style]


def _nonempty_text(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def validate_brief(brief: Any) -> dict[str, Any]:
    """Validate model- or human-authored brief data at the pipeline boundary."""
    if not isinstance(brief, dict):
        raise ValueError("brief must be a JSON object")
    missing = REQUIRED_BRIEF_KEYS - brief.keys()
    if missing:
        raise ValueError(f"missing brief fields: {sorted(missing)}")

    for key in TEXT_BRIEF_KEYS & brief.keys():
        _nonempty_text(brief[key], f"brief.{key}")
    for key in ("base_color", "accent"):
        if key not in brief:
            continue
        value = brief[key]
        if isinstance(value, str):
            _nonempty_text(value, f"brief.{key}")
        elif not isinstance(value, list) or not value:
            raise ValueError(f"brief.{key} must be a non-empty string or list of strings")
        else:
            for index, item in enumerate(value, 1):
                _nonempty_text(item, f"brief.{key}[{index}]")

    sections = brief.get("sections", [])
    if not isinstance(sections, list):
        raise ValueError("brief.sections must be a list")
    for index, section in enumerate(sections, 1):
        if not isinstance(section, dict):
            raise ValueError(f"brief section {index} must be an object")
        if "heading" not in section:
            raise ValueError(f"brief section {index} has no 'heading'")
        _nonempty_text(section["heading"], f"brief section {index}.heading")
        lines = section.get("lines", [])
        if not isinstance(lines, list):
            raise ValueError(f"brief section {index}.lines must be a list")
        for line_index, line in enumerate(lines, 1):
            _nonempty_text(line, f"brief section {index}.lines[{line_index}]")

    aspect = brief.get("aspect")
    if aspect is not None:
        if not isinstance(aspect, str) or (aspect != "auto" and ratio(aspect) is None):
            raise ValueError("brief.aspect must be 'auto' or a positive W:H ratio")

    layout = brief.get("layout")
    if layout is not None and (not isinstance(layout, str) or layout not in ARRANGEMENTS):
        valid = ", ".join(sorted(ARRANGEMENTS))
        raise ValueError(f"brief.layout must be one of: {valid}")
    position = brief.get("diagram_position")
    if position is not None and (not isinstance(position, str) or position not in DIAGRAM_POSITIONS):
        valid = ", ".join(sorted(DIAGRAM_POSITIONS))
        raise ValueError(f"brief.diagram_position must be one of: {valid}")
    return brief


def recipe_from_brief(
    brief: Any,
    *,
    style: str,
    model: str = DEFAULT_MODEL,
    n: int = 4,
    name: str = "generated",
    description: str | None = None,
) -> Recipe:
    """Build a validated recipe from a generated or hand-authored brief."""
    if not isinstance(style, str) or style not in FAMILY_KEYS:
        raise ValueError(f"style must be one of: {', '.join(FAMILY_KEYS)}")
    if not isinstance(model, str) or model not in MODEL_ASPECTS:
        raise ValueError(f"unknown model {model!r}")
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= MODEL_ASPECTS[model].n_max:
        raise ValueError(f"n must be an integer from 1 through {MODEL_ASPECTS[model].n_max}")
    _nonempty_text(name, "name")
    if description is not None:
        _nonempty_text(description, "description")
    return Recipe(
        name=name,
        style=style,
        brief=validate_brief(brief),
        model=model,
        n=n,
        description=description,
    )


def load_recipe(path: pathlib.Path | str) -> Recipe:
    path = pathlib.Path(path)
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"recipe {path} must contain a JSON object")
    try:
        style = data["style"]
    except KeyError as exc:
        raise ValueError(f"recipe {path} missing field: style") from exc
    try:
        return recipe_from_brief(
            data.get("brief", {}),
            style=style,
            model=data.get("model", DEFAULT_MODEL),
            n=data.get("n", 4),
            name=data.get("name", path.stem),
            description=data.get("description"),
        )
    except ValueError as exc:
        raise ValueError(f"recipe {path}: {exc}") from exc
