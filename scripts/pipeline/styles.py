import json
import pathlib

from scripts.pipeline.recipe import FAMILY_KEYS


def load_styles(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


def get_family(styles: dict, letter: str) -> dict:
    return styles["families"][FAMILY_KEYS[letter]]
