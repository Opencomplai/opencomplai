"""`opencomplai generate oscal` -- OSCAL assessment-results from an artifact."""

from __future__ import annotations

from pathlib import Path

import typer
from opencomplai_core.oscal_export import build_assessment_results, to_json

from opencomplai_cli.commands.generate import app, fail
from opencomplai_cli.inputs import read_json_file


@app.command("oscal")
def oscal(
    artifact: Path = typer.Argument(
        ..., help="Path to a compliance-artifact.json written by `check --with-gaps`"
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Write the document to this file instead of stdout"
    ),
) -> None:
    """Write one OSCAL 1.1.2 assessment-results JSON document.

    One result per framework, one finding per requirement row. The output is
    not validated against the NIST OSCAL schema by this command.
    """
    try:
        raw = read_json_file(artifact)
        if not isinstance(raw, dict):
            raise ValueError("not a compliance artifact")
        text = to_json(build_assessment_results(raw))
    except (OSError, ValueError) as e:
        fail(str(e))
    if out is None:
        typer.echo(text, nl=False)
        return
    try:
        out.write_text(text, encoding="utf-8", newline="")
    except OSError as e:
        fail(str(e))
