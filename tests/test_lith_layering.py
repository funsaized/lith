"""Keep lith's rendering core independent from I/O and provider layers."""

from __future__ import annotations

import ast
from pathlib import Path


PURE_MODULES = ("render", "aspect", "layout", "recipe", "styles", "paths")
FORBIDDEN_LAYER_PREFIXES = ("lith.cli", "lith.call")
NETWORK_MODULE_PREFIXES = (
    "aiohttp",
    "ftplib",
    "http",
    "httpx",
    "requests",
    "smtplib",
    "socket",
    "telnetlib",
    "urllib",
    "websockets",
    "xmlrpc",
)
NETWORK_SYMBOLS = {
    "HTTPConnection",
    "HTTPSConnection",
    "create_connection",
    "urlopen",
    "urlretrieve",
}
LITH_ROOT = Path(__file__).resolve().parents[1] / "src" / "lith"


def _matches_prefix(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)


def _import_targets(node: ast.Import | ast.ImportFrom) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}

    if node.level:
        # Every guarded file is directly inside the ``lith`` package, so one
        # leading dot resolves from that package.
        base = "lith"
        if node.module:
            base = f"{base}.{node.module}"
    else:
        base = node.module or ""

    targets = {base} if base else set()
    for alias in node.names:
        if alias.name != "*":
            targets.add(f"{base}.{alias.name}" if base else alias.name)
    return targets


def _dotted_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for target in _import_targets(node):
                if _matches_prefix(target, FORBIDDEN_LAYER_PREFIXES):
                    violations.add(f"imports provider/CLI layer {target!r}")
                if _matches_prefix(target, NETWORK_MODULE_PREFIXES):
                    violations.add(f"imports network module {target!r}")
        elif isinstance(node, ast.Attribute):
            name = _dotted_name(node)
            if name and _matches_prefix(name, FORBIDDEN_LAYER_PREFIXES):
                violations.add(f"references provider/CLI layer {name!r}")
            if name and _matches_prefix(name, NETWORK_MODULE_PREFIXES):
                violations.add(f"references network module {name!r}")
        elif isinstance(node, ast.Name) and node.id in NETWORK_SYMBOLS:
            violations.add(f"references network symbol {node.id!r}")

    return sorted(violations)


def test_pure_modules_do_not_depend_on_io_layers():
    failures = {
        module: violations
        for module in PURE_MODULES
        if (violations := _violations(LITH_ROOT / f"{module}.py"))
    }
    assert not failures, "pure-module layering violations: " + "; ".join(
        f"{module}: {', '.join(violations)}"
        for module, violations in failures.items()
    )
