"""Credential resolution for image providers.

Resolution is deliberately read-only and tiered: shell, repository ``.env``,
Hermes ``.env``, then Hermes' OAuth pool.  The first usable credential wins.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class _Provider:
    variable: str
    base_url_prefix: str


PROVIDERS: dict[str, _Provider] = {
    "xai": _Provider("XAI_API_KEY", "https://api.x.ai/v1"),
    "openai": _Provider("OPENAI_API_KEY", "https://api.openai.com/v1"),
    "minimax": _Provider("MINIMAX_API_KEY", "https://api.minimax.io/v1"),
}


class MissingCredential(ValueError):
    """Raised after all four credential tiers have been searched."""


class CredentialFileError(ValueError):
    """Raised when a credential file exists but cannot be parsed safely."""


@dataclass(frozen=True)
class Credential:
    """A resolved secret plus inspectable, non-secret provenance."""

    provider: str
    secret: str = field(repr=False)
    tier: int
    source: str
    auth_type: str
    organization_id: str | None = None
    project_id: str | None = None

    @property
    def fingerprint(self) -> str:
        """A short stable fingerprint suitable for ``lith-call --auth``."""
        return sha256(self.secret.encode("utf-8")).hexdigest()[:8]

    @property
    def is_oauth(self) -> bool:
        return self.auth_type == "oauth"


def find_repo_root(
    recipe_path: str | os.PathLike[str] | None = None,
    *,
    cwd: str | os.PathLike[str] | None = None,
) -> Path | None:
    """Find the nearest repository root, anchored to a recipe when supplied."""
    working_dir = Path(cwd) if cwd is not None else Path.cwd()
    working_dir = working_dir.expanduser().resolve()
    if recipe_path is not None:
        recipe = Path(recipe_path).expanduser()
        if not recipe.is_absolute():
            recipe = working_dir / recipe
        start = recipe.resolve().parent
    else:
        start = working_dir if working_dir.is_dir() else working_dir.parent

    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").is_file():
            return candidate
    return None


def _read_env(path: Path) -> dict[str, str]:
    """Read the small dotenv subset needed for API credentials."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise CredentialFileError(f"cannot read credential file {path}: {exc}") from exc

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, raw_value = line.partition("=")
        key = key.strip()
        if not separator or not key:
            continue
        value = raw_value.strip()
        if value[:1] in {"'", '"'}:
            quote = value[0]
            if len(value) < 2 or value[-1] != quote:
                raise CredentialFileError(
                    f"unterminated quoted value in {path} at line {line_number}"
                )
            value = value[1:-1]
        values[key] = value
    return values


def _from_values(
    provider: str,
    values: Mapping[str, str],
    *,
    tier: int,
    source: str,
) -> Credential | None:
    variable = PROVIDERS[provider].variable
    secret = values.get(variable, "").strip()
    if not secret:
        return None
    organization_id = None
    project_id = None
    if provider == "openai":
        organization_id = values.get("OPENAI_ORG_ID") or None
        project_id = values.get("OPENAI_PROJECT_ID") or None
    return Credential(
        provider=provider,
        secret=secret,
        tier=tier,
        source=source,
        auth_type="api_key",
        organization_id=organization_id,
        project_id=project_id,
    )


def _pool_entries(pool: Any) -> list[tuple[str, Mapping[str, Any]]]:
    if isinstance(pool, Mapping):
        entries = []
        for name, value in pool.items():
            if isinstance(value, Mapping):
                entries.append((str(name), value))
                continue
            if isinstance(value, list):
                for entry in value:
                    if not isinstance(entry, Mapping):
                        continue
                    entries.append((str(name), entry))
        return entries
    if isinstance(pool, list):
        entries = []
        for index, entry in enumerate(pool):
            if not isinstance(entry, Mapping):
                continue
            name = entry.get("name") or entry.get("id") or str(index)
            entries.append((str(name), entry))
        return entries
    return []


def _entry_matches_provider(name: str, entry: Mapping[str, Any], provider: str) -> bool:
    declared = entry.get("provider")
    if isinstance(declared, str):
        lowered_declared = declared.lower()
        return (
            lowered_declared == provider
            or lowered_declared.startswith(f"{provider}-")
        )
    lowered = name.lower()
    return lowered == provider or lowered.startswith(f"{provider}-")


def _base_url_matches(base_url: Any, prefix: str) -> bool:
    if not isinstance(base_url, str):
        return False
    normalized = base_url.rstrip("/")
    required = prefix.rstrip("/")
    return normalized == required or normalized.startswith(f"{required}/")


def _from_auth_json(provider: str, path: Path) -> Credential | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise CredentialFileError(f"cannot parse credential file {path}: {exc}") from exc
    if not isinstance(document, Mapping):
        return None

    required_base = PROVIDERS[provider].base_url_prefix
    for name, entry in _pool_entries(document.get("credential_pool")):
        if not _entry_matches_provider(name, entry, provider):
            continue
        # api_key entries contain only fingerprints and provenance, never a key.
        if entry.get("auth_type") != "oauth":
            continue
        if not _base_url_matches(entry.get("base_url"), required_base):
            continue
        secret = entry.get("access_token")
        if not isinstance(secret, str) or not secret.strip():
            continue
        return Credential(
            provider=provider,
            secret=secret.strip(),
            tier=4,
            source=f"~/.hermes/auth.json:{name}",
            auth_type="oauth",
        )
    return None


def resolve_credential(
    provider: str,
    *,
    recipe_path: str | os.PathLike[str] | None = None,
    cwd: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    home: str | os.PathLike[str] | None = None,
) -> Credential:
    """Resolve ``provider`` from the first usable tier.

    ``home`` and ``environ`` are injectable so tests and callers can make the
    search deterministic without consulting the developer's real credentials.
    """
    normalized_provider = provider.lower()
    if normalized_provider not in PROVIDERS:
        valid = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"unknown provider {provider!r}; expected one of {valid}")

    environment = os.environ if environ is None else environ
    found = _from_values(
        normalized_provider,
        environment,
        tier=1,
        source="shell environment",
    )
    if found is not None:
        return found

    repo_root = find_repo_root(recipe_path, cwd=cwd)
    repo_env = repo_root / ".env" if repo_root is not None else None
    if repo_env is not None:
        found = _from_values(
            normalized_provider,
            _read_env(repo_env),
            tier=2,
            source=str(repo_env),
        )
        if found is not None:
            return found

    home_dir = Path(home).expanduser() if home is not None else Path.home()
    hermes_dir = home_dir / ".hermes"
    hermes_env = hermes_dir / ".env"
    found = _from_values(
        normalized_provider,
        _read_env(hermes_env),
        tier=3,
        source="~/.hermes/.env",
    )
    if found is not None:
        return found

    auth_json = hermes_dir / "auth.json"
    found = _from_auth_json(normalized_provider, auth_json)
    if found is not None:
        return found

    variable = PROVIDERS[normalized_provider].variable
    repo_location = str(repo_env) if repo_env is not None else "<repo>/.env (no root found)"
    raise MissingCredential(
        f"missing {variable} for {normalized_provider}; searched "
        f"tier 1 shell environment; tier 2 {repo_location}; "
        "tier 3 ~/.hermes/.env; tier 4 ~/.hermes/auth.json"
    )
