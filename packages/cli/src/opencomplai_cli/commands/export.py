"""`opencomplai export` -- write one neutral evidence package from an artifact.

Moves data, never gates: exit 0 whatever the verdict inside. Reads only the
artifact path it is given; writes only `--out` and `--artifact-out`. Nothing is
sent anywhere. `err_console` comes lazily from `opencomplai_cli.main` (a
module-level import back into main would be circular).
"""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from pathlib import Path

import typer
from opencomplai_core.evidence_package import build_evidence_package, package_to_csv
from rich.markup import escape

from opencomplai_cli.inputs import read_json_file


class ExportFormat(StrEnum):
    json = "json"
    csv = "csv"


def export_cmd(
    artifact: Path = typer.Argument(
        ..., help="Path to a compliance-artifact.json written by `check --with-gaps`"
    ),
    fmt: ExportFormat = typer.Option(
        ExportFormat.json,
        "--format",
        help="json (the package) or csv (one row per article)",
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Write the package to this file instead of stdout"
    ),
    artifact_out: Path | None = typer.Option(
        None,
        "--artifact-out",
        help="Also write the embedded artifact, ready for `opencomplai verify`",
    ),
) -> None:
    """Export one neutral, schema-validated evidence package (JSON or CSV)."""
    from opencomplai_cli import main as _main

    try:
        raw = read_json_file(artifact)
        pkg = build_evidence_package(raw)
    except (OSError, ValueError) as e:
        _main.err_console.print(f"[red]Error:[/red] {escape(str(e))}")
        sys.exit(2)

    if fmt == ExportFormat.csv:
        text = package_to_csv(pkg)
    else:
        text = pkg.model_dump_json(indent=2) + "\n"
    try:
        if artifact_out is not None:
            # Same bytes semantics the signature covers: parses to the same model.
            artifact_out.write_text(
                json.dumps(pkg.artifact, indent=2) + "\n",
                encoding="utf-8",
                newline="",
            )
        if out is not None:
            out.write_text(text, encoding="utf-8", newline="")
    except OSError as e:
        _main.err_console.print(f"[red]Error:[/red] {escape(str(e))}")
        sys.exit(2)
    if out is None:
        typer.echo(text, nl=False)
