import pathlib
import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    """Lowercase, collapse non-alnum to single underscore, trim."""
    s = text.strip().lower()
    s = _SLUG_RE.sub("_", s)
    return s.strip("_") or "untitled"


def output_path(
    out_dir: pathlib.Path | str, family_key: str, headline: str, ext: str
) -> pathlib.Path:
    return pathlib.Path(out_dir) / f"{family_key}_{slug(headline)}{ext}"


def default_output_dir(recipe_path: pathlib.Path | str) -> pathlib.Path:
    """Anchor outputs to the recipe rather than the caller's cwd.

    An agent's working directory is arbitrary, so deriving from it scatters
    artifacts wherever the session happened to start. A recipe in a directory
    named ``recipes`` publishes to its sibling ``outputs``; anything else
    publishes beside the recipe.
    """
    base = pathlib.Path(recipe_path).resolve().parent
    root = base.parent if base.name == "recipes" else base
    return root / "outputs"
