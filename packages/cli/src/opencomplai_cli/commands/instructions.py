"""`opencomplai instructions generate`: Art. 13(3) instructions-for-use pack.

`console`/`err_console` are obtained lazily from `opencomplai_cli.main` (it
imports this module to register the sub-typer, so a top-level import is circular).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import typer
from opencomplai_core.instructions_for_use import (
    generate_instructions_for_use,
    render_instructions_for_use_markdown,
)
from opencomplai_core.models import SystemManifest

app = typer.Typer(help="Art. 13 instructions-for-use commands.")


class OutputFormat(StrEnum):
    human = "human"
    json = "json"


@app.command("generate")
def generate_cmd(
    manifest_file: Path = typer.Option(
        Path("system-manifest.json"),
        "--manifest",
        "-m",
        help="Path to system manifest JSON file",
    ),
    # Not docs/ and not instructions*: those names satisfy the Art. 13 file probe.
    output_dir: Path = typer.Option(Path("./instructions-for-use"), "--output-dir"),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Draft Art. 13(3) instructions for use from the system manifest.

    Every point the manifest does not capture is listed as "not captured",
    never fabricated. Informational draft, not legal advice.
    """
    from opencomplai_cli import main as _main

    if not manifest_file.exists():
        _main.err_console.print(
            f"[red]Error:[/red] manifest file not found: {manifest_file}"
        )
        _main.err_console.print("Run [bold]opencomplai init[/bold] first.")
        sys.exit(2)
    try:
        manifest = SystemManifest.model_validate(
            json.loads(manifest_file.read_text(encoding="utf-8"))
        )
    except Exception as e:
        _main.err_console.print(f"[red]Validation error:[/red] {e}")
        sys.exit(2)

    doc = generate_instructions_for_use(
        manifest, generated_at=datetime.now(UTC).isoformat()
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "instructions_for_use.json"
    md_path = output_dir / "instructions_for_use.md"
    json_path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(render_instructions_for_use_markdown(doc), encoding="utf-8")

    if output == OutputFormat.json:
        print(doc.model_dump_json(indent=2))
        return
    by_id = {p.point: p for p in doc.points}
    _main.console.print(
        f"[bold]Populated {doc.populated_point_count} of {doc.total_points} "
        "Art. 13(3) points[/bold]"
    )
    _main.console.print(f"  {json_path}")
    _main.console.print(f"  {md_path}")
    for pid in doc.not_captured_points:
        _main.console.print(
            f"  not captured: {pid} ({by_id[pid].element})", soft_wrap=True
        )
