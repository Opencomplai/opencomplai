"""
`opencomplai agents` -- inventory, check and report over the manifest's
declared agent inventory.

Everything here is offline: it reads the manifest (and an optional scan report)
from disk and never touches the evidence vault or the network. The commands
only read, validate, cross-check and render what `opencomplai_core.agent_*`
already provide; no verdict is computed (output is evidence only).

`opencomplai_cli.main` is imported LAZILY inside the helpers (as in
`commands/qms.py`) because main.py imports this module's `app`.
"""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Any

import typer
from opencomplai_core.agent_report import (
    NOT_A_VERDICT,
    build_agent_report,
    render_agent_report_markdown,
)
from opencomplai_core.models import CorroborationReport, SystemManifest

app = typer.Typer(help="Agent inventory commands (offline; evidence only).")


class OutputFormat(StrEnum):
    human = "human"
    json = "json"


class ReportFormat(StrEnum):
    markdown = "markdown"
    json = "json"


_MANIFEST = typer.Option(
    Path("system-manifest.json"), "--manifest", "-m", help="System manifest JSON"
)
_SCAN = typer.Option(
    None,
    "--scan-report",
    help="Optional CorroborationReport JSON (from `opencomplai check --scan`) "
    "to cross-check the declared inventory against.",
)


def _fail(msg: str) -> None:
    from opencomplai_cli import main as _main

    _main.err_console.print(f"[red]Error:[/red] {msg}", markup=True, highlight=False)
    sys.exit(2)


def _load(
    manifest_file: Path, scan_file: Path | None
) -> tuple[SystemManifest, CorroborationReport | None]:
    from opencomplai_cli import main as _main
    from opencomplai_cli.inputs import load_manifest, read_json_file

    if not manifest_file.exists():
        _fail(f"manifest file not found: {manifest_file}")
    try:
        manifest = load_manifest(manifest_file)
    except Exception as e:
        _fail(f"invalid manifest: {e}")
    scan = None
    if scan_file is not None:
        try:
            scan = CorroborationReport.model_validate(read_json_file(scan_file))
        except Exception as e:
            _main.err_console.print(
                f"Warning: failed to parse {scan_file}: {e}", markup=False
            )
    return manifest, scan


def _echo_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@app.command("inventory")
def inventory_cmd(
    manifest_file: Path = _MANIFEST,
    scan_report_file: Path | None = _SCAN,
    output_format: OutputFormat = typer.Option(
        OutputFormat.human, "--output-format", "-o"
    ),
) -> None:
    """List the declared agents: parent tree, tools, models and mandate."""
    manifest, scan = _load(manifest_file, scan_report_file)
    agents = build_agent_report(manifest, scan)["inventory"]
    if output_format == OutputFormat.json:
        _echo_json({"system_id": manifest.system_id, "agents": agents})
        return
    if not agents:
        typer.echo("no agent inventory declared")
        return
    ids = {a["id"] for a in agents}
    children: dict[str | None, list[dict]] = {}
    for a in agents:
        # A dangling parent is shown at the top level; `check` reports it.
        children.setdefault(
            a["parent_id"] if a["parent_id"] in ids else None, []
        ).append(a)

    def show(a: dict, depth: int) -> None:
        typer.echo(
            f"{'  ' * depth}- {a['id']} ({a['name']}) | tools: "
            f"{', '.join(a['tools']) or '-'} | models: {', '.join(a['models']) or '-'}"
            f" | mandate: {'yes' if a['has_mandate'] else 'no'}"
        )
        for c in children.get(a["id"], []):
            show(c, depth + 1)

    for root in children.get(None, []):
        show(root, 0)
    # Agents in a parent cycle have no root and would recurse forever: flat.
    shown = _reachable(children)
    for a in agents:
        if a["id"] not in shown:
            typer.echo(f"- {a['id']} ({a['name']}) | parent cycle; see `agents check`")


def _reachable(children: dict[str | None, list[dict]]) -> set[str]:
    out: set[str] = set()
    stack = list(children.get(None, []))
    while stack:
        a = stack.pop()
        if a["id"] not in out:
            out.add(a["id"])
            stack.extend(children.get(a["id"], []))
    return out


@app.command("check")
def check_cmd(
    manifest_file: Path = _MANIFEST,
    scan_report_file: Path | None = _SCAN,
    output_format: OutputFormat = typer.Option(
        OutputFormat.human, "--output-format", "-o"
    ),
) -> None:
    """Validate the inventory and cross-check it against a scan report.

    Exit 2: missing or invalid manifest or inventory. Exit 1: declared-versus-
    detected findings. Exit 0: none. Never a compliance verdict.
    """
    manifest, scan = _load(manifest_file, scan_report_file)
    findings = build_agent_report(manifest, scan)["findings"]
    invalid = [f for f in findings if f["kind"] == "invalid_inventory"]
    code = 2 if invalid else 1 if findings else 0
    if output_format == OutputFormat.json:
        _echo_json(
            {
                "system_id": manifest.system_id,
                "notice": NOT_A_VERDICT,
                "findings": findings,
                "exit_code": code,
            }
        )
    else:
        for f in findings:
            typer.echo(f"[{f['evidence']}] {f['kind']}: {f['detail']}")
        typer.echo(f"{len(findings)} finding(s); {NOT_A_VERDICT}.")
    raise typer.Exit(code)


@app.command("report")
def report_cmd(
    manifest_file: Path = _MANIFEST,
    scan_report_file: Path | None = _SCAN,
    fmt: ReportFormat = typer.Option(ReportFormat.markdown, "--format"),
    output_file: Path | None = typer.Option(
        None, "--output", help="Write here instead of stdout"
    ),
) -> None:
    """Inventory, findings and the responsibility map (with review flags)."""
    manifest, scan = _load(manifest_file, scan_report_file)
    report = build_agent_report(manifest, scan)
    text = (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
        if fmt == ReportFormat.json
        else render_agent_report_markdown(report)
    )
    if output_file is None:
        typer.echo(text, nl=False)
    else:
        output_file.write_text(text, encoding="utf-8")
