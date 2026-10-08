"""`opencomplai rules changelog` -- the rule-set history, oldest to newest."""

from __future__ import annotations

import json
import sys
from enum import StrEnum

import typer
from opencomplai_core.ruleset_history import entries_since
from rich.markup import escape

app = typer.Typer(help="Rule-set history commands.")


class OutputFormat(StrEnum):
    human = "human"
    json = "json"
    markdown = "markdown"


def _meta(e: dict) -> str:
    review = "; needs founder review" if e.get("needs_founder_review") else ""
    return f"source: {e['source']}; confidence: {e['confidence']}{review}"


@app.command("changelog")
def changelog_cmd(
    since: str | None = typer.Option(
        None, "--since", "-s", help="Only versions newer than this one, e.g. 1.5.0"
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """List what changed in each rule-set version, oldest first."""
    from opencomplai_cli import main as _main

    try:
        entries = entries_since(since)
    except ValueError as e:
        _main.err_console.print(f"[red]Error:[/red] --since: {escape(str(e))}")
        sys.exit(2)
    if output == OutputFormat.json:
        typer.echo(json.dumps(entries, indent=2))
    elif output == OutputFormat.markdown:
        for e in entries:
            typer.echo(f"## {e['version']}\n\n{e['summary']}\n")
            for c in e["changes"]:
                typer.echo(f"- {c}")
            typer.echo(f"\n_{_meta(e)}_\n")
    else:
        for e in entries:
            _main.console.print(
                f"[bold]{escape(e['version'])}[/bold]  {escape(e['summary'])}"
            )
            for c in e["changes"]:
                _main.console.print(f"  - {escape(c)}")
            _main.console.print(f"  {escape(_meta(e))}\n")
