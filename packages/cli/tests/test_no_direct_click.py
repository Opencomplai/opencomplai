"""typer 0.27 no longer ships click, so a direct import is an undeclared dependency."""

import ast
import re
import tomllib
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def test_cli_does_not_import_click():
    bad = []
    for f in SRC.rglob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in n.names]
                if isinstance(n, ast.Import)
                else [n.module or ""]
                if isinstance(n, ast.ImportFrom) and not n.level
                else []
            )
            if any(x == "click" or x.startswith("click.") for x in names):
                bad.append(f"{f}:{n.lineno}")
    assert not bad, (
        "direct click import (typer 0.27 no longer ships click, so this is an "
        "undeclared dependency; use typer.Context): " + ", ".join(bad)
    )


def test_cli_does_not_import_typer_private_click():
    bad = []
    for f in SRC.rglob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                hit = any(a.name.startswith("typer._click") for a in n.names)
            elif isinstance(n, ast.ImportFrom) and not n.level:
                mod = n.module or ""
                hit = mod.startswith("typer._click") or (
                    mod == "typer" and any(a.name == "_click" for a in n.names)
                )
            else:
                continue
            if hit:
                bad.append(f"{f}:{n.lineno}")
    assert not bad, "typer-private click import: " + ", ".join(bad)


def test_cli_typer_dependency_is_unpinned_and_click_free():
    deps = tomllib.loads((SRC.parents[0] / "pyproject.toml").read_text("utf-8"))[
        "project"
    ]["dependencies"]
    names = [re.split(r"[\s<>=!~;\[]", d, maxsplit=1)[0].lower() for d in deps]
    assert "click" not in names, "click must not be declared (typer owns it)"
    typer = [d for d in deps if d.lower().startswith("typer")]
    assert typer, "typer dependency missing"
    assert not any("<" in d or "==" in d for d in typer), typer
