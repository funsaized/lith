import json
import pathlib
from dataclasses import dataclass

FAMILY_KEYS = {
    "A": "A_sticker",
    "B": "B_brutalist",
    "C": "C_patent",
    "D": "D_manga",
    "E": "E_screenshot",
    "F": "F_woodcut",
    "G": "G_log",
}

REQUIRED_BRIEF_KEYS = {"topic", "headline", "icon", "aspect"}



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


def load_recipe(path: pathlib.Path | str) -> Recipe:
    path = pathlib.Path(path)
    data = json.loads(path.read_text())
    brief = data.get("brief", {})
    missing = REQUIRED_BRIEF_KEYS - brief.keys()
    if missing:
        raise ValueError(f"recipe {path} missing brief fields: {sorted(missing)}")
    return Recipe(
        name=data.get("name", path.stem),
        style=data["style"],
        brief=brief,
        model=data.get("model", "grok-imagine-image-quality"),
        n=data.get("n", 4),
        description=data.get("description"),
    )
