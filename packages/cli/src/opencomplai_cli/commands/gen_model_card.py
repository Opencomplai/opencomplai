"""`opencomplai generate model-card`: a model card from the system manifest."""

from __future__ import annotations

import json
from datetime import date
from enum import StrEnum
from pathlib import Path

import typer
from opencomplai_core.model_card import build_model_card, render_model_card_markdown
from opencomplai_core.models import SystemManifest

from opencomplai_cli.commands.generate import app, fail


class OutputFormat(StrEnum):
    human = "human"
    json = "json"


@app.command("model-card")
def model_card_cmd(
    manifest_file: Path = typer.Option(
        Path("manifest.json"), "--manifest", "-m", help="System manifest JSON"
    ),
    output_file: Path = typer.Option(
        Path("MODEL_CARD.md"), "--output", "-o", help="Path to write the model card"
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.human, "--output-format"),
) -> None:
    """Write a Markdown model card with YAML front matter from the manifest."""
    if not manifest_file.exists():
        fail(f"manifest file not found: {manifest_file}")
    try:
        manifest = SystemManifest.model_validate(
            json.loads(manifest_file.read_text(encoding="utf-8"))
        )
    except Exception as exc:
        fail(f"invalid manifest: {exc}")

    card = build_model_card(manifest, today=date.today())
    with output_file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(render_model_card_markdown(card))

    if output_format == OutputFormat.json:
        payload = {
            "system_id": card.system_id,
            "commit_ref": card.commit_ref,
            "generated_on": card.generated_on,
            "output": str(output_file),
            "sections": [
                {
                    "key": s.key,
                    "title": s.title,
                    "source": s.source,
                    "populated": s.populated,
                }
                for s in card.sections
            ],
            "metrics": card.metrics,
            "provenance": card.provenance,
        }
        typer.echo(json.dumps(payload, indent=2))
    else:
        populated = sum(1 for s in card.sections if s.populated)
        typer.echo(
            f"Wrote {output_file} ({populated} of {len(card.sections)} sections "
            "filled from the manifest)."
        )
