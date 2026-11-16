"""`opencomplai scaffold <FW> [DOC]` -- write a pack's fill-in scaffolds.

`console` and `err_console` come lazily from `opencomplai_cli.main`.
"""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

import typer
from rich.markup import escape


class ScaffoldFormat(StrEnum):
    human = "human"
    json = "json"


def scaffold_cmd(
    framework: str = typer.Argument(
        ..., help="Framework key, for example ISO_IEC_42001."
    ),
    doc: str | None = typer.Argument(
        None, help="Document id; omit for every document."
    ),
    list_only: bool = typer.Option(
        False, "--list", help="List document ids, titles and targets; write nothing."
    ),
    output_dir: Path = typer.Option(
        Path("."), "--output-dir", help="Directory the targets are written under."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
    output: ScaffoldFormat = typer.Option(
        ScaffoldFormat.human, "--output", help="human or json."
    ),
) -> None:
    """Write a framework pack's fill-in scaffolds (placeholder: _fill in_)."""
    from opencomplai_core.pack_registry import pack_dir
    from opencomplai_core.pack_scaffolds import list_scaffolds, write_scaffolds

    from opencomplai_cli.main import console, err_console

    def fail(message: str) -> NoReturn:
        err_console.print(f"[red]{escape(message)}[/red]")
        raise typer.Exit(2)

    if not re.fullmatch(r"\w+", framework) or not pack_dir(framework).is_dir():
        fail(f"Unknown framework {framework!r}")
    try:
        entries = list_scaffolds(framework)
    except ValueError as exc:
        fail(str(exc))
    if not entries:
        fail(f"{framework} ships no scaffolds")
    if doc is not None and doc not in entries:
        fail(f"Unknown document {doc!r} for {framework}; known: {', '.join(entries)}")

    if list_only:
        if output == ScaffoldFormat.json:
            documents = [
                {"id": i, "title": e["title"], "target": e["target"]}
                for i, e in entries.items()
            ]
            typer.echo(
                json.dumps({"framework": framework, "documents": documents}, indent=2)
            )
        else:
            for i, e in entries.items():
                console.print(
                    escape(f"{i}\t{e['title']}\t{e['target']}"), soft_wrap=True
                )
        return

    docs = [doc] if doc is not None else list(entries)
    try:
        results = write_scaffolds(framework, docs, output_dir, force=force)
    except ValueError as exc:
        fail(str(exc))
    created = [p for p, s in results if s == "created"]
    skipped = [p for p, s in results if s == "skipped"]
    if output == ScaffoldFormat.json:
        typer.echo(
            json.dumps(
                {"framework": framework, "created": created, "skipped": skipped},
                indent=2,
            )
        )
        return
    for p in created:
        console.print(escape(f"created {p}"), soft_wrap=True)
    for p in skipped:
        console.print(escape(f"skipped {p} (exists; use --force)"), soft_wrap=True)
