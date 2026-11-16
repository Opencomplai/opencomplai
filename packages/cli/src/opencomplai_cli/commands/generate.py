"""
`opencomplai generate` -- a command group filled by module discovery.

Every `gen_*.py` module in this package is imported once, at the bottom of
this file. A generator module does
`from opencomplai_cli.commands.generate import app, fail` and decorates its
function with `@app.command("<name>")`.

Generators move data and never gate: exit 0 on success, exit 2 on unreadable
input. A generator module that fails to import is a hard error.

`err_console` is obtained lazily because `main.py` imports command modules, so
a module-level import back into `main` would be circular.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from types import ModuleType
from typing import NoReturn

import typer
from rich.markup import escape

app = typer.Typer(
    help="Generate documents and exports from the manifest and the artifact.",
    no_args_is_help=True,
)


def fail(message: str) -> NoReturn:
    """Print `Error: <message>` on the error console and exit 2."""
    from opencomplai_cli import main as _main

    _main.err_console.print(f"Error: {escape(message)}")
    sys.exit(2)


def discover(package: ModuleType) -> list[str]:
    """Import every `gen_*` module of `package`; return the imported names."""
    names = sorted(
        info.name
        for info in pkgutil.iter_modules(package.__path__)
        if info.name.startswith("gen_")
    )
    imported: list[str] = []
    for name in names:
        full = f"{package.__name__}.{name}"
        importlib.import_module(full)
        imported.append(full)
    return imported


def _discover_commands() -> list[str]:
    from opencomplai_cli import commands

    return discover(commands)


_discover_commands()
