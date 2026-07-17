"""AST import and callsite extraction (Python)."""

from __future__ import annotations

import ast
from pathlib import Path

from opencomplai_core.scanner.feature_types import CallsiteRef, FrameworkObjectRef, ImportRef
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


class _FrameworkObjectVisitor(ast.NodeVisitor):
    """Joins `var = ClassName(...)` bindings to later `var.method(...)` calls.

    Scoped to a single function/module body (an `ast.NodeVisitor` naturally resets its
    binding table per `visit_FunctionDef`/`visit_AsyncFunctionDef` since each starts a
    fresh instance) — this intentionally does not track cross-function data flow (e.g. a
    variable passed as an argument into another function). That is a known limitation of
    this v1: it only detects the "construct and invoke in the same function or module
    body" pattern, not arbitrary object flow.
    """

    def __init__(self, rel_path: str, scope, class_names: frozenset[str]) -> None:
        self.rel_path = rel_path
        self.scope = scope
        self.class_names = class_names
        self.results: list[FrameworkObjectRef] = []
        self._bindings: dict[str, tuple[str, str]] = {}  # var_name -> (class_name, location)

    def _record_binding(self, target: ast.expr, value: ast.expr) -> None:
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
            return
        func = value.func
        class_name = None
        if isinstance(func, ast.Name):
            class_name = func.id
        elif isinstance(func, ast.Attribute):
            class_name = func.attr
        if class_name in self.class_names:
            self._bindings[target.id] = (class_name, f"{self.rel_path}:{value.lineno}")

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._record_binding(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None and node.target is not None:
            self._record_binding(node.target, node.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            binding = self._bindings.get(func.value.id)
            if binding is not None:
                class_name, instantiation_location = binding
                self.results.append(
                    FrameworkObjectRef(
                        class_name=class_name,
                        method_name=func.attr,
                        var_name=func.value.id,
                        instantiation_location=instantiation_location,
                        invocation_location=f"{self.rel_path}:{node.lineno}",
                        scope=self.scope,
                    )
                )
        self.generic_visit(node)


def _parse_framework_objects(
    path: Path, rel_path: str, scope, class_names: frozenset[str]
) -> list[FrameworkObjectRef]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=rel_path)
    except (OSError, SyntaxError):
        return []

    visitor = _FrameworkObjectVisitor(rel_path, scope, class_names)
    visitor.visit(tree)
    return visitor.results


def extract_ast_framework_objects(
    inventory: RepoInventory, class_names: frozenset[str]
) -> list[FrameworkObjectRef]:
    """Extract variables constructed from `class_names` and later invoked via method call.

    Additive sibling to `extract_ast_callsites` — does not replace or alter the existing
    lexical `CallsiteRef` extraction, which remains the fast-path/fallback signal.
    """
    results: list[FrameworkObjectRef] = []
    for entry in inventory.entries:
        if entry.language != "python" or entry.is_binary:
            continue
        results.extend(
            _parse_framework_objects(Path(entry.path), entry.rel_path, entry.scope, class_names)
        )
    return results
