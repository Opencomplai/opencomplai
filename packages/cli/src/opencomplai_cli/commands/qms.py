"""
`opencomplai qms generate` -- CP-15.

Renders the Art. 17(1)(a)-(m) quality-management-system document by directly
reusing CP-7's per-clause probes (`qms_article_17_clause_statuses`, via
`opencomplai_core.qms_document`) -- never re-derives clause status, so this
command can't disagree with what `opencomplai recommend`/`opencomplai gaps`
already report for the same repo.

Templated on `commands/controls.py` for the Typer/console/output-format
conventions; `console`/`err_console` are obtained LAZILY inside the command
via `from opencomplai_cli import main as _main` (not at module load time)
because `main.py` imports this module's `app` to register the `qms`
sub-typer, so a module-level import back into `main` would be circular.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import typer
from opencomplai_core.control_catalog import get_catalog
from opencomplai_core.models import CorroborationReport, EvalReport
from opencomplai_core.qms_document import (
    build_qms_document,
    render_qms_document_markdown,
)
from rich.table import Table

app = typer.Typer(help="Art. 17 quality-management-system document commands.")


class OutputFormat(StrEnum):
    """CLI output format -- mirrors `opencomplai_cli.main.OutputFormat`'s values."""

    human = "human"
    json = "json"


def _evidence_hashes(
    scan_report: CorroborationReport | None, eval_report: EvalReport | None
) -> list[str]:
    """SHA-256 evidence-object hashes, sourced exactly like `generate_dossier`
    (doc-generator) does: the scan report's own hash plus each evaluator
    result's evidence hash. No new evidence-vault client -- same inputs
    `opencomplai check --scan`/`--sample-set` already write to disk."""
    hashes: list[str] = []
    if scan_report is not None:
        hashes.append(scan_report.report_hash)
    if eval_report is not None:
        hashes.extend(r.evidence_hash for r in eval_report.results)
    return hashes


@app.command("generate")
def generate_cmd(
    system_id: str = typer.Option(
        "", "--system-id", help="System identifier (document header only)"
    ),
    commit_ref: str = typer.Option("HEAD", "--commit-ref", help="Git commit reference"),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo-root",
        help="Repository root for the Art. 17(1)(a)-(m) per-clause artifact "
        "probes -- the same probes `opencomplai recommend`/`opencomplai "
        "gaps` use for Art. 17",
    ),
    scan_report_file: Path = typer.Option(
        Path("scan-report.json"),
        "--scan-report",
        help="Optional CorroborationReport JSON (written by `opencomplai "
        "check --scan`); its report_hash is cited as evidence when present. "
        "Absence stays honest -- never fabricated.",
    ),
    eval_report_file: Path = typer.Option(
        Path("eval-report.json"),
        "--eval-report",
        help="Optional EvalReport JSON (written by `opencomplai check "
        "--sample-set ...`); its per-evaluator evidence hashes are cited "
        "when present. Absence stays honest -- never fabricated.",
    ),
    output_file: Path = typer.Option(
        Path("qms-document.md"),
        "--output",
        "-o",
        help="Path to write the rendered Markdown document",
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.human, "--output-format"),
) -> None:
    """Generate a filled Art. 17(1)(a)-(m) QMS document: per-clause evidence
    status (present/missing/partial) for each of the 13 sub-points, not a
    single article-level verdict."""
    from opencomplai_cli import main as _main

    scan_report: CorroborationReport | None = None
    if scan_report_file.exists():
        try:
            scan_report = CorroborationReport.model_validate(
                json.loads(scan_report_file.read_text())
            )
        except Exception as exc:
            _main.err_console.print(
                f"[yellow]Warning:[/yellow] failed to parse {scan_report_file}: {exc}"
            )

    eval_report: EvalReport | None = None
    if eval_report_file.exists():
        try:
            eval_report = EvalReport.model_validate(
                json.loads(eval_report_file.read_text())
            )
        except Exception as exc:
            _main.err_console.print(
                f"[yellow]Warning:[/yellow] failed to parse {eval_report_file}: {exc}"
            )

    resolved_repo_root = repo_root.resolve()
    doc = build_qms_document(
        resolved_repo_root,
        system_id=system_id,
        commit_ref=commit_ref,
        generated_at=datetime.now(UTC).isoformat(),
        evidence_hashes=_evidence_hashes(scan_report, eval_report),
    )

    markdown = render_qms_document_markdown(doc)
    output_file.write_text(markdown, encoding="utf-8")

    if output_format == OutputFormat.json:
        payload = {
            "system_id": doc.system_id,
            "commit_ref": doc.commit_ref,
            "generated_at": doc.generated_at,
            "clauses": [
                {
                    "clause": f"Art. 17(1)({c.letter})",
                    "title": c.title,
                    "status": c.status.value,
                    "status_label": c.status_label,
                    "evidence_ref": c.evidence_ref,
                    "rationale": c.rationale,
                }
                for c in doc.clauses
            ],
            "present_count": doc.present_count,
            "missing_count": doc.missing_count,
            "unverified_count": doc.unverified_count,
            "evidence_hashes": doc.evidence_hashes,
            "output_file": str(output_file),
        }
        _main.console.print_json(json.dumps(payload))
        return

    catalog_entry = get_catalog().get("Art. 17")
    title = catalog_entry.title if catalog_entry else "Quality management system"
    _main.console.print(f"\n[bold]Art. 17 -- {title}[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim")
    table.add_column("QMS element")
    table.add_column("Status", min_width=10)
    table.add_column("Evidence", style="dim")
    for clause in doc.clauses:
        table.add_row(
            f"({clause.letter})", clause.title, clause.status_label, clause.evidence_ref
        )
    _main.console.print(table)

    summary = f"{doc.present_count} present / {doc.missing_count} missing"
    if doc.unverified_count:
        summary += f" / {doc.unverified_count} unverified"
    _main.console.print(
        f"\n[bold]{summary}[/bold] (of 13 clauses) -- wrote {output_file}\n"
    )
