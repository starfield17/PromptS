"""Minimal example architecture test.

Adapt module names to the repository. This intentionally avoids a heavy framework.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

FORBIDDEN = {
    "app.modules.training": ("app.modules.deploy.internal",),
    "app.modules.deploy": ("app.modules.training.internal",),
}


def imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def module_name(path: Path) -> str:
    rel = path.relative_to(SRC).with_suffix("")
    return ".".join(rel.parts)


def test_forbidden_imports() -> None:
    violations: list[str] = []

    for path in SRC.rglob("*.py"):
        owner = module_name(path)
        imported = imports_in(path)

        for source_prefix, forbidden_prefixes in FORBIDDEN.items():
            if not owner.startswith(source_prefix):
                continue
            for imported_name in imported:
                for forbidden in forbidden_prefixes:
                    if imported_name == forbidden or imported_name.startswith(forbidden + "."):
                        violations.append(
                            f"{path.relative_to(ROOT)}: {source_prefix} must not import {imported_name}"
                        )

    assert not violations, "ARCHITECTURE VIOLATION:\n" + "\n".join(violations)
