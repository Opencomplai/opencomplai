"""Interactive init flow: checker wizard then manifest prompts."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from opencomplai_core.compliance_checker import bridge_to_manifest_fields
from opencomplai_core.models import CheckerSessionRef, SystemManifest
from rich.console import Console

from opencomplai_cli.commands.checker import (
    build_checker_session_ref,
    display_results,
    evaluate_and_finalize,
    run_interactive_wizard,
    write_exports,
)

console = Console()


def run_interactive_init(
    *,
    skip_checker: bool,
    output_file: Path,
    compliance_target: str,
    section_extras: dict | None,
    signing_setup_fn,
) -> None:
    """Run checker wizard (optional) then collect manifest fields interactively."""
    checker_result = None
    report_path: Path | None = None

    if not skip_checker:
        session = run_interactive_wizard(skip_allowed=True)
        if session is not None:
            checker_result = evaluate_and_finalize(session)
            display_results(checker_result)
            report_path = output_file.parent / "eu-ai-act-result.json"
            write_exports(checker_result, export_json=report_path)
            bridged = bridge_to_manifest_fields(checker_result)
            default_purpose = bridged.get("intended_purpose", "")
            default_role = bridged.get("operator_role", "")
            default_hr = bridged.get("high_risk_presumption", False)
        else:
            default_purpose = ""
            default_role = ""
            default_hr = False
    else:
        default_purpose = ""
        default_role = ""
        default_hr = False

    system_id = typer.prompt("System ID", default="my-ai-system")
    intended_purpose = typer.prompt(
        "Intended purpose (Annex III mapping)",
        default=str(default_purpose) if default_purpose else "",
    )
    high_risk = typer.confirm(
        "Presume high-risk classification?",
        default=bool(default_hr),
    )

    manifest_data: dict = {
        "system_id": system_id,
        "intended_purpose": intended_purpose,
        "compliance_target": compliance_target,
        "high_risk_presumption": high_risk,
        "commit_ref": "HEAD",
    }
    if default_role and default_role != "unknown":
        manifest_data["operator_role"] = default_role

    if checker_result is not None:
        manifest_data["checker_session"] = CheckerSessionRef.model_validate(
            build_checker_session_ref(checker_result, report_path)
        ).model_dump()

    if section_extras:
        manifest_data.update(section_extras)

    manifest = SystemManifest.model_validate(manifest_data)
    output_file.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    console.print(f"\n[green]Manifest written to[/green] {output_file}")
    if checker_result:
        console.print("Checker session embedded. Next: [bold]opencomplai check[/bold]")
