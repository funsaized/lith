import json
import pathlib
from importlib import resources

from .recipe import FAMILY_KEYS


def load_styles(path: pathlib.Path | str | None = None) -> dict:
    """Load the bundled style families, or an explicit styles file."""
    if path is None:
        text = resources.files("lith").joinpath("data/styles.json").read_text(
            encoding="utf-8"
        )
    else:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    return json.loads(text)


def get_family(styles: dict, letter: str) -> dict:
    return styles["families"][FAMILY_KEYS[letter]]
