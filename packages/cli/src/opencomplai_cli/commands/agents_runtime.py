"""
`opencomplai agents import-log` and `opencomplai agents dispute-report`.

Offline, read-only side tools for a runtime governance toolkit's file audit
sink (JSONL) or a native agent decision log. Nothing here feeds `check`, `gaps`,
a dossier or a push payload, and imported evidence never exceeds PARTIAL. Exit
0 whenever the file was read (rejected lines and UNVERIFIED are reported, never
fatal); exit 2 only for unreadable input or a usage error. `main` is not
imported (main.py imports this module's group).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from opencomplai_core.agent_dispute_report import (
    build_dispute_report,
    import_native,
    parse_bound,
    render_markdown,
)
from opencomplai_core.bridges.agt import ImportResult, import_jsonl, parse_map

from opencomplai_cli.commands.agents import OutputFormat, ReportFormat
from opencomplai_cli.commands.agents import app as agents_app

_MAP = typer.Option(
    None,
    "--map",
    help="Override a field's dotted path, e.g. --map ts=data.when (repeatable). "
    "Fields: ts, agent_id, action, decision, rule, told, approver.",
)


def _usage(msg: str) -> None:
    typer.echo(f"Error: {msg}", err=True)
    sys.exit(2)


def _read(path: Path, source: str, maps: list[str] | None) -> ImportResult:
    if source not in ("agt", "native"):
        _usage(f"unsupported --source {source!r}")
    if source == "native" and maps:
        _usage("--map applies to --source agt only")
    try:
        mapping = parse_map(maps or [])
    except ValueError as exc:
        _usage(str(exc))
    if not path.is_file():
        _usage(f"cannot read {path}: not a file")
    try:
        return (
            import_native(path) if source == "native" else import_jsonl(path, mapping)
        )
    except OSError as exc:
        _usage(f"cannot read {path}: {exc.__class__.__name__}")


def _emit(text: str, output: Path | None) -> None:
    if output is None:
        typer.echo(text, nl=False)
        return
    try:
        with open(output, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    except OSError as exc:
        _usage(f"cannot write {output}: {exc.__class__.__name__}")


def import_log_cmd(
    file: Path = typer.Argument(..., help="Audit log (JSON lines); one file, no globs"),
    source: str = typer.Option("agt", "--source", help="Only 'agt' is supported"),
    map_: list[str] = _MAP,
    fmt: OutputFormat = typer.Option(OutputFormat.human, "--format"),
    output: Path | None = typer.Option(None, "--output", help="Write to FILE"),
) -> None:
    """Read and summarise a runtime audit log. Evidence is capped at PARTIAL; exit 0 or 2."""
    if source != "agt":
        _usage(f"unsupported --source {source!r} (only 'agt')")
    res = _read(file, "agt", map_)
    if fmt == OutputFormat.json:
        body = {
            "source": source,
            "file_sha256": res.file_sha256,
            "total_lines": res.total_lines,
            "mapped": len(res.records),
            "rejected": res.rejected,
            "rejected_samples": [
                {"line": n, "reason": r} for n, r in res.rejected_samples
            ],
            "integrity": res.integrity,
            "status": res.status.value,
            "caveats": list(res.caveats),
        }
        text = json.dumps(body, indent=2) + "\n"
    else:
        lines = [
            f"file sha256: {res.file_sha256}",
            f"lines: {res.total_lines}, mapped: {len(res.records)}, "
            f"rejected: {res.rejected}",
            *(f"  rejected line {n}: {r}" for n, r in res.rejected_samples),
            f"integrity: {res.integrity}",
            f"status: {res.status.value.upper()} (capped; never met)",
            "limits:",
            *(f"  - {c}" for c in res.caveats),
        ]
        text = "\n".join(lines) + "\n"
    _emit(text, output)


def dispute_report_cmd(
    log: Path = typer.Option(..., "--log", help="Audit log (JSON lines)"),
    from_: str = typer.Option(
        ..., "--from", help="Window start (ISO date or datetime)"
    ),
    to: str = typer.Option(
        ..., "--to", help="Window end, inclusive (date = whole day)"
    ),
    source: str = typer.Option("agt", "--source", help="agt or native"),
    agent: str | None = typer.Option(None, "--agent", help="Only this agent id"),
    map_: list[str] = _MAP,
    fmt: ReportFormat = typer.Option(ReportFormat.markdown, "--format"),
    output: Path | None = typer.Option(None, "--output", help="Write to FILE"),
) -> None:
    """Render what each agent was told, decided and why. Evidence only; exit 0 or 2."""
    try:
        start, end = parse_bound(from_, end=False), parse_bound(to, end=True)
    except ValueError as exc:
        _usage(str(exc))
    if start > end:
        _usage("--from is after --to")
    res = _read(log, source, map_)
    report = build_dispute_report(
        res.records,
        start=start,
        end=end,
        agent_id=agent,
        source_label=source,
        file_sha256=res.file_sha256,
        integrity=res.integrity,
        rejected=res.rejected,
        caveats=res.caveats,
    )
    if fmt == ReportFormat.json:
        text = json.dumps(report.to_json_dict(), indent=2, sort_keys=True) + "\n"
    else:
        text = render_markdown(report)
    _emit(text, output)


agents_app.command("import-log")(import_log_cmd)
agents_app.command("dispute-report")(dispute_report_cmd)
