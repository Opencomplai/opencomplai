"""Import-isolation guards — `opencomplai check` must stay air-gap / deterministic."""

from __future__ import annotations

import ast
from pathlib import Path

import opencomplai_core.engine as engine_module

_FORBIDDEN_SUBSTRINGS = (
    "inspect_eval",
    "bridges.inspect_eval",
    "inspect_ai",
    "local_dashboard",
    "opencomplai_cli.updates",
)


def _module_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_engine_never_imports_bridge_or_serve_or_updates():
    source = _module_source(Path(engine_module.__file__))
    for needle in _FORBIDDEN_SUBSTRINGS:
        assert needle not in source, f"engine.py must not reference {needle!r}"


def test_engine_ast_has_no_forbidden_imports():
    tree = ast.parse(_module_source(Path(engine_module.__file__)))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    joined = " ".join(imported)
    assert "inspect_ai" not in joined
    assert "bridges" not in joined
    assert "local_dashboard" not in joined
