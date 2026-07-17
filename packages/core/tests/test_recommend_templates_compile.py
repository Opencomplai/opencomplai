"""Compile-check every shipped Python remediation template."""

from __future__ import annotations

import ast
from pathlib import Path

_TEMPLATES = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "opencomplai_core"
    / "templates"
    / "recommend"
    / "python"
)


def test_all_python_templates_parse():
    py_files = sorted(_TEMPLATES.rglob("*.py"))
    assert py_files, "expected shipped python templates"
    for path in py_files:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        compile(source, str(path), "exec")
