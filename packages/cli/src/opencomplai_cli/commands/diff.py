"""`opencomplai diff` -- compare two artifacts or gap reports.

Read-only. Prints no date: the inputs' `generated_at` is never shown.
`console`/`err_console` come lazily from `opencomplai_cli.main` (a module-level
import back into main would be circular).
"""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from pathlib import Path

import typer
from opencomplai_core.gap_diff import diff_gap_reports
from opencomplai_core.models import FrameworkReport, GapReport
from rich.markup import escape
from rich.table import Table

from opencomplai_cli.inputs import read_json_file


class DiffFormat(StrEnum):
    human = "human"
    json = "json"
    markdown = "markdown"


def _load_side(
    path: Path,
) -> tuple[GapReport, dict[str, FrameworkReport], str | None]:
    """(gap report, framework reports, rule_set_version or None). Raises ValueError."""
    raw = read_json_file(path)
    if isinstance(raw, dict) and "gap_report" in raw:
        if raw["gap_report"] is None:
            raise ValueError(
                f"{path}: artifact has no gap_report; run `opencomplai check --with-gaps`"
            )
        rsv = raw.get("rule_set_version")
        frameworks = raw.get("frameworks") or {}
        return (
            GapReport.model_validate(raw["gap_report"]),
            {k: FrameworkReport.model_validate(v) for k, v in frameworks.items()},
            rsv if isinstance(rsv, str) else None,
        )
    from opencomplai_cli import main as _main

    report, frameworks = _main._read_gap_report(path)
    return report, frameworks, None


def _rule_set_line(rs: dict) -> str:
    if rs["changed"] is None:
        return "unknown (input carries no rule_set_version)"
    if not rs["changed"]:
        return f"unchanged ({rs['to']})"
    return f"{rs['from']} -> {rs['to']}: rules changed"


def _markdown(d: dict) -> str:
    out = ["# Gap report diff", "", f"Rule set: {_rule_set_line(d['rule_set'])}", ""]
    for entry in d["rule_set"]["changes"]:
        out.append(f"- {entry['version']}: {entry['summary']}")
    if d["rule_set"]["changes"]:
        out.append("")
    out += ["## Changed", ""]
    if d["changed"]:
        out += ["| Article | From | To | Direction |", "|---|---|---|---|"]
        out += [
            f"| {c['article']} | {c['from']} | {c['to']} | {c['direction']} |"
            for c in d["changed"]
        ]
    else:
        out.append("None.")
    for title, key in (("Added", "added"), ("Removed", "removed")):
        out += ["", f"## {title}", ""]
        if d[key]:
            out += ["| Article | Status |", "|---|---|"]
            out += [f"| {r['article']} | {r['status']} |" for r in d[key]]
        else:
            out.append("None.")
    out += ["", f"Unchanged: {d['unchanged_count']}"]
    return "\n".join(out)


def _human(console, d: dict) -> None:
    console.print(f"Rule set: {escape(_rule_set_line(d['rule_set']))}")
    for entry in d["rule_set"]["changes"]:
        console.print(f"  {escape(entry['version'])}: {escape(entry['summary'])}")
    if d["changed"]:
        table = Table(title="Changed verdicts")
        for col in ("Article", "From", "To", "Direction"):
            table.add_column(col)
        for c in d["changed"]:
            table.add_row(escape(c["article"]), c["from"], c["to"], c["direction"])
        console.print(table)
    else:
        console.print("No changed verdicts.")
    for title, key in (("Added", "added"), ("Removed", "removed")):
        if d[key]:
            console.print(f"{title}:")
            for r in d[key]:
                console.print(f"  {escape(r['article'])} ({r['status']})")
    console.print(f"Unchanged: {d['unchanged_count']}")


def diff_cmd(
    file_a: Path = typer.Argument(..., help="Older artifact or gap report (JSON)"),
    file_b: Path = typer.Argument(..., help="Newer artifact or gap report (JSON)"),
    output: DiffFormat = typer.Option(DiffFormat.human, "--output", "-o"),
    fail_on_regression: bool = typer.Option(
        False,
        "--fail-on-regression",
        help="Exit 1 when any verdict got worse",
    ),
) -> None:
    """Compare two artifacts or gap reports: added, removed and changed verdicts."""
    from opencomplai_cli import main as _main

    try:
        ra, fa, va = _load_side(file_a)
        rb, fb, vb = _load_side(file_b)
    except (OSError, ValueError) as e:  # pydantic.ValidationError is a ValueError
        _main.err_console.print(f"[red]Error:[/red] {escape(str(e))}")
        sys.exit(2)
    d = diff_gap_reports(ra, rb, a_rule_set=va, b_rule_set=vb, extra_a=fa, extra_b=fb)
    if output == DiffFormat.json:

        def side(p: Path, r: GapReport) -> dict:
            return {
                "path": str(p),
                "system_id": r.system_id,
                "commit_ref": r.commit_ref,
            }

        typer.echo(
            json.dumps({"a": side(file_a, ra), "b": side(file_b, rb), **d}, indent=2)
        )
    elif output == DiffFormat.markdown:
        typer.echo(_markdown(d))
    else:
        _human(_main.console, d)
    if fail_on_regression and d["regression"]:
        sys.exit(1)
