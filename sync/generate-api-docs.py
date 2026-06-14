#!/usr/bin/env python3
"""Generate API documentation from Python docstrings."""

import ast
from pathlib import Path
from typing import Any


def extract_functions(source_file: Path) -> list[dict[str, Any]]:
    """Extract function signatures and docstrings."""

    tree = ast.parse(source_file.read_text())
    functions = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):  # Skip private functions
                continue

            docstring = ast.get_docstring(node) or "No documentation"

            # Extract arguments
            args = []
            for arg in node.args.args:
                if arg.arg != "self":  # Skip 'self' for methods
                    type_hint = ""
                    if arg.annotation:
                        if isinstance(arg.annotation, ast.Name):
                            type_hint = arg.annotation.id
                        elif isinstance(arg.annotation, ast.Constant):
                            type_hint = str(arg.annotation.value)

                    args.append({"name": arg.arg, "type": type_hint or "Any"})

            # Extract return type
            returns = ""
            if node.returns:
                if isinstance(node.returns, ast.Name):
                    returns = node.returns.id

            functions.append(
                {
                    "name": node.name,
                    "docstring": docstring,
                    "args": args,
                    "returns": returns,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "lineno": node.lineno,
                }
            )

    return functions


def extract_classes(source_file: Path) -> list[dict[str, Any]]:
    """Extract class definitions."""
    tree = ast.parse(source_file.read_text())
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue

            docstring = ast.get_docstring(node) or "No documentation"

            classes.append(
                {"name": node.name, "docstring": docstring, "lineno": node.lineno}
            )

    return classes


def generate_markdown(
    functions: list[dict[str, Any]],
    module_name: str,
    classes: list[dict[str, Any]] | None = None,
) -> str:
    """Generate Markdown documentation."""

    md = f"# {module_name} API Reference\n\n"
    md += f"Auto-generated API reference for `{module_name}`.\n\n"

    if classes is None:
        classes = []

    if not functions and not classes:
        md += "> Auto-generated from module docstrings. Direct function definitions not found.\n"
        md += "> Import the module and explore available classes and functions.\n"
        return md

    # Functions section
    if functions:
        md += "## Functions\n\n"
        for func in functions:
            md += f"- [`{func['name']}`](#{func['name'].lower()})\n"
        md += "\n"

        # Function details
        for func in functions:
            md += f"### `{func['name']}`\n\n"

            # Signature
            args_str = ", ".join(
                [f"{arg['name']}: {arg['type']}" for arg in func["args"]]
            )
            async_prefix = "async " if func["is_async"] else ""
            returns_str = f" -> {func['returns']}" if func["returns"] else ""
            md += f"```python\n{async_prefix}def {func['name']}({args_str}){returns_str}:\n    ...\n```\n\n"

            # Docstring
            md += f"{func['docstring']}\n\n"

            # Arguments table
            if func["args"]:
                md += "**Arguments:**\n\n"
                md += "| Name | Type | Description |\n"
                md += "|------|------|-------------|\n"
                for arg in func["args"]:
                    md += f"| `{arg['name']}` | {arg['type']} | |\n"
                md += "\n"

            # Return type
            if func["returns"]:
                md += f"**Returns:** `{func['returns']}`\n\n"

            md += "---\n\n"

    # Classes section
    if classes:
        md += "## Classes\n\n"
        for cls in classes:
            md += f"- [`{cls['name']}`](#{cls['name'].lower()})\n"
        md += "\n"

        for cls in classes:
            md += f"### `{cls['name']}`\n\n"
            md += f"{cls['docstring']}\n\n"
            md += "---\n\n"

    return md


def find_main_module(package_path: Path) -> Path:
    """Find the main __init__.py in a package."""
    candidates = [
        package_path / "src" / "__init__.py",
        package_path / "__init__.py",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Try to find it in nested src/module structure
    src_dir = package_path / "src"
    if src_dir.exists():
        for subdir in src_dir.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("_"):
                init_file = subdir / "__init__.py"
                if init_file.exists():
                    return init_file

    return None


def main():
    """Generate API documentation for all packages."""

    packages = [
        ("packages/core", "OpenComplai Core"),
        ("packages/sdk-python", "Python SDK"),
        ("packages/cli", "CLI Tools"),
    ]

    for package_path, display_name in packages:
        pkg_dir = Path(package_path)
        if not pkg_dir.exists():
            print(f"[SKIP] {package_path} (not found)")
            continue

        # Find main module
        main_py = find_main_module(pkg_dir)

        if main_py is None:
            print(f"[SKIP] {package_path} (no __init__.py found)")
            continue

        # Extract functions and classes
        functions = extract_functions(main_py)
        classes = extract_classes(main_py)

        # Generate markdown
        markdown = generate_markdown(functions, display_name, classes)

        # Write to docs
        output_file = Path("docs/api") / f"{display_name.lower().replace(' ', '-')}.md"
        output_file.write_text(markdown)

        print(
            f"[OK] Generated: {output_file} ({len(functions)} functions, {len(classes)} classes)"
        )


if __name__ == "__main__":
    main()
    print("\n[OK] API documentation generated!")
