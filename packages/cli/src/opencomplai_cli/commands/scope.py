"""`opencomplai scope <FW>` -- answer a pack's applicability and scope questions.

Writes the answers to `framework_inputs.<FW>.scope` in the manifest and prints
the framework outcome and the rows the answers take out. `console` and
`err_console` come lazily from `opencomplai_cli.main` (a module-level import
back into main would be circular).
"""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from pathlib import Path

import typer
from rich.markup import escape

from opencomplai_cli.inputs import read_json_file


class ScopeFormat(StrEnum):
    human = "human"
    json = "json"


_YES_NO = {"yes": True, "no": False}


def _parse_answers(pairs: list[str], declared: dict) -> dict[str, bool]:
    """KEY=yes|no pairs to booleans. Raises ValueError on a bad pair or key."""
    parsed: dict[str, bool] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise ValueError(f"--answer {pair!r} must look like KEY=yes or KEY=no")
        if key not in declared:
            raise ValueError(
                f"unknown scope key {key!r}; known keys: {', '.join(declared)}"
            )
        if value not in _YES_NO:
            raise ValueError(f"--answer {key}: value must be yes or no, not {value!r}")
        parsed[key] = _YES_NO[value]
    return parsed


def _question_keys(fw: str, requirements: dict | None) -> list[str]:
    """Pack questions in file order, then shared keys by first use in scope_out."""
    from opencomplai_core.applicability import load_applicability

    data = load_applicability(fw)
    keys = [q["key"] for q in data["questions"]] if data else []
    for config in (requirements or {}).values():
        for group in config.get("scope_out", []):
            for key in group:
                if key not in keys:
                    keys.append(key)
    return keys


def _prompt(keys: list[str], declared: dict, current: dict, given: dict) -> dict:
    asked: dict[str, bool] = {}
    for key in keys:
        if key in given:
            continue
        default = "" if key not in current else ("yes" if current[key] else "no")
        while True:
            reply = (
                typer.prompt(
                    f"{declared[key]['text']}? (yes/no, empty keeps it unanswered)",
                    default=default,
                    show_default=bool(default),
                )
                .strip()
                .lower()
            )
            if reply == "":
                break
            if reply in _YES_NO:
                asked[key] = _YES_NO[reply]
                break
            typer.echo("Answer yes or no.")
    return asked


def scope_cmd(
    framework: str = typer.Argument(
        ..., help="Framework key, for example ISO_IEC_27090"
    ),
    manifest: Path = typer.Option(
        Path("system-manifest.json"), "--manifest", help="Manifest to update"
    ),
    answer: list[str] = typer.Option(
        [], "--answer", help="KEY=yes|no; repeatable. Skips the prompt for that key"
    ),
    output: ScopeFormat = typer.Option(ScopeFormat.human, "--output", "-o"),
) -> None:
    """Answer a framework's scope questions and show the rows they take out."""
    from opencomplai_core.applicability import (
        applicability_outcome,
        declared_scope_keys,
    )
    from opencomplai_core.frameworks import (
        EU_AI_ACT,
        FRAMEWORKS,
        evaluate_targets,
        pack_requirements,
    )
    from opencomplai_core.models import FrameworkScope, SystemManifest

    from opencomplai_cli import main as _main

    def fail(message: str) -> None:
        _main.err_console.print(f"[red]Error:[/red] {escape(message)}")
        sys.exit(2)

    if framework == EU_AI_ACT:
        fail(
            "EU_AI_ACT has no scope questions; use `opencomplai checker` for its "
            "applicability checker."
        )
    if framework not in FRAMEWORKS:
        fail(f"unknown framework {framework}; known: {', '.join(FRAMEWORKS)}")
    try:
        raw = read_json_file(manifest)
        if not isinstance(raw, dict):
            raise ValueError(f"{manifest}: must be a JSON object")
        declared = declared_scope_keys(framework)
        given = _parse_answers(answer, declared)
        requirements = pack_requirements(FRAMEWORKS[framework])
        keys = _question_keys(framework, requirements)
    except (OSError, ValueError) as e:
        fail(str(e))

    inputs = raw.setdefault("framework_inputs", {})
    entry = inputs.setdefault(framework, {})
    scope_raw = entry.setdefault("scope", {})
    try:
        current = FrameworkScope.model_validate(scope_raw).answers()
    except ValueError as e:
        fail(f"{manifest}: framework_inputs.{framework}.scope: {e}")

    if output == ScopeFormat.human and sys.stdin.isatty():
        given = {**_prompt(keys, declared, current, given), **given}
    scope_raw.update(given)
    for key in [k for k, v in scope_raw.items() if v is None]:
        del scope_raw[key]
    if not scope_raw:
        del entry["scope"]
    if not entry:
        del inputs[framework]
    if not inputs:
        del raw["framework_inputs"]

    try:
        model = SystemManifest.model_validate(raw)
        report = evaluate_targets(model, [framework], commit_ref="scope")[framework]
    except (OSError, ValueError) as e:
        fail(str(e))
    answers = FrameworkScope.model_validate(
        ((raw.get("framework_inputs") or {}).get(framework) or {}).get("scope") or {}
    ).answers()
    result = applicability_outcome(framework, answers)

    manifest.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    scoped_out = dict(report.excluded)
    total = len(report.report.articles) + len(scoped_out)
    if output == ScopeFormat.json:
        typer.echo(
            json.dumps(
                {
                    "framework": framework,
                    "outcome": result[0] if result else None,
                    "reason": result[1] if result else None,
                    "scope": answers,
                    "scoped_out": scoped_out,
                },
                indent=2,
            )
        )
        return
    if result:
        _main.console.print(
            f"Outcome: {escape(result[0])}"
            + (f" - {escape(result[1])}" if result[1] else "")
        )
    _main.console.print(
        f"{len(scoped_out)} of {total} requirements are out of scope"
        + (":" if scoped_out else "")
    )
    for rid, reason in scoped_out.items():
        _main.console.print(f"  {escape(rid)}: {escape(reason)}")
