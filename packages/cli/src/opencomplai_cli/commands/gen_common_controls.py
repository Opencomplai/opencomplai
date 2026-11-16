"""`opencomplai generate common-controls` -- rows that share an evidence source."""

from __future__ import annotations

import json
from dataclasses import asdict
from enum import StrEnum
from pathlib import Path

import typer
from opencomplai_core.common_controls import CommonControl, build_common_controls

from opencomplai_cli.commands.generate import app, fail
from opencomplai_cli.inputs import read_json_file


class CommonControlsFormat(StrEnum):
    human = "human"
    json = "json"


def _table(controls: list[CommonControl]) -> str:
    header = ("ref", "kind", "frameworks", "rows")
    lines = [
        (c.ref, c.kind, ", ".join(c.frameworks), str(len(c.rows))) for c in controls
    ]
    table = [header, *lines]
    widths = [max(len(r[i]) for r in table) for i in range(len(header))]
    return "\n".join(
        "  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)).rstrip()
        for r in table
    )


@app.command("common-controls")
def common_controls(
    artifact: Path | None = typer.Option(
        None, "--artifact", help="A compliance-artifact.json; adds each row's status"
    ),
    output_format: CommonControlsFormat = typer.Option(
        CommonControlsFormat.human, "--output-format", help="human or json"
    ),
    min_frameworks: int = typer.Option(
        1, "--min-frameworks", min=1, help="Keep controls cited by this many frameworks"
    ),
) -> None:
    """List the evidence sources that pack rows cite, with the rows that share each."""
    try:
        raw = read_json_file(artifact) if artifact is not None else None
        controls = build_common_controls(artifact=raw)
    except (OSError, ValueError) as e:
        fail(str(e))
    controls = [c for c in controls if len(c.frameworks) >= min_frameworks]
    if output_format == CommonControlsFormat.json:
        typer.echo(json.dumps([asdict(c) for c in controls], indent=2))
    else:
        typer.echo(_table(controls))
