"""AST import and callsite extraction (Python)."""

from __future__ import annotations

import ast
from pathlib import Path

from opencomplai_core.scanner.feature_types import CallsiteRef, ImportRef
from opencomplai_core.scanner.inventory import RepoInventory


def _parse_python(
    path: Path, rel_path: str, scope
) -> tuple[list[ImportRef], list[CallsiteRef]]:
    imports: list[ImportRef] = []
    callsites: list[CallsiteRef] = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=rel_path)
    except (OSError, SyntaxError):
        return imports, callsites

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ImportRef(
                        module=alias.name,
                        location=f"{rel_path}:{node.lineno}",
                        scope=scope,
                    )
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(
                ImportRef(
                    module=node.module,
                    location=f"{rel_path}:{node.lineno}",
                    scope=scope,
                )
            )
        elif isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name:
                callsites.append(
                    CallsiteRef(
                        name=name,
                        location=f"{rel_path}:{node.lineno}",
                        scope=scope,
                    )
                )
    return imports, callsites


def _collect_ast(inventory: RepoInventory) -> tuple[list[ImportRef], list[CallsiteRef]]:
    imports: list[ImportRef] = []
    callsites: list[CallsiteRef] = []
    for entry in inventory.entries:
        if entry.language != "python" or entry.is_binary:
            continue
        file_imports, file_calls = _parse_python(
            Path(entry.path), entry.rel_path, entry.scope
        )
        imports.extend(file_imports)
        callsites.extend(file_calls)
    return imports, callsites


def extract_ast_imports(inventory: RepoInventory) -> list[ImportRef]:
    imports, _ = _collect_ast(inventory)
    return imports


def extract_ast_callsites(inventory: RepoInventory) -> list[CallsiteRef]:
    _, callsites = _collect_ast(inventory)
    return callsites
