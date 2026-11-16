"""`opencomplai generate impact-assessment`: a fill-in draft from the manifest."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer

from opencomplai_cli.commands.generate import app, fail


@app.command("impact-assessment")
def impact_assessment(
    kind: str = typer.Option(..., "--kind", help="ai-system or dpia."),
    manifest_file: Path = typer.Option(
        Path("manifest.json"), "--manifest", help="System manifest to pre-fill from."
    ),
    output_dir: Path = typer.Option(
        Path("assessments"), "--output-dir", help="Where the .md and .json go."
    ),
) -> None:
    """Write impact_assessment_<kind>.md and .json, pre-filled from the manifest."""
    from opencomplai_core.impact_assessment import (
        KINDS,
        build_assessment,
        render_assessment_markdown,
    )

    from opencomplai_cli.inputs import load_manifest

    if kind not in KINDS:
        fail(f"unknown kind {kind!r}; use one of: {', '.join(KINDS)}")
    if not manifest_file.exists():
        fail(f"manifest file not found: {manifest_file}")
    try:
        manifest = load_manifest(manifest_file)
    except Exception as exc:
        fail(f"manifest validation error: {exc}")

    document = build_assessment(
        kind, manifest, generated_at=datetime.now(UTC).isoformat(timespec="seconds")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / f"impact_assessment_{kind}.md"
    json_path = output_dir / f"impact_assessment_{kind}.json"
    md_path.write_text(render_assessment_markdown(document), encoding="utf-8")
    json_path.write_text(document.model_dump_json(indent=2) + "\n", encoding="utf-8")
    typer.echo(f"Wrote {md_path} and {json_path}")
