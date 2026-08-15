import pathlib
import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    """Lowercase, collapse non-alnum to single underscore, trim."""
    s = text.strip().lower()
    s = _SLUG_RE.sub("_", s)
    return s.strip("_") or "untitled"


def output_path(
    out_dir: pathlib.Path, family_key: str, headline: str, ext: str
) -> pathlib.Path:
    return out_dir / f"{family_key}_{slug(headline)}{ext}"
