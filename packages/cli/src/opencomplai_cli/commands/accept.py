"""
`opencomplai accept`: write a signed, committable acceptance record.

The record (see ``opencomplai_core.acceptance``) is bound to the manifest
fingerprint and lives in the repository, so `opencomplai check` can honour it
on ephemeral CI. A prohibited (Art. 5) system can never be accepted. With
``--trap-approval`` the same record type carries an approval of a flagged
change; `check` honours it for the same `--change-context` (see `acceptance_gate`).

Helpers from `main` (`console`, `err_console`, `_SIGNING_KEY`) are reached
lazily, as in `commands/halt.py`, to avoid a circular import.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import typer
from opencomplai_core.acceptance import (
    CLASSIFICATION_ACCEPTANCE,
    TRAP_APPROVAL,
    build_record,
    key_id_for,
    public_key_pem_from_private,
    record_path,
    sign_record,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.engine import assess
from opencomplai_core.models import AssessmentInput, ModelMetadata, RiskLevel
from opencomplai_core.signing import SigningKeyError, resolve_key

from opencomplai_cli.commands.halt import OutputFormat


def _main_module():
    from opencomplai_cli import main as _main

    return _main


def _fail(message: str) -> None:
    _main_module().err_console.print(f"[red]Error:[/red] {message}")
    sys.exit(2)


def _is_prohibited(manifest) -> bool:
    cs = manifest.checker_session
    verdict = cs.verdict if cs is not None else None
    if "prohibited_practice" in (verdict, manifest.intended_purpose):
        return True
    risk = assess(
        AssessmentInput(
            model=ModelMetadata(
                name=manifest.system_id,
                version="HEAD",
                modality="text",
                use_case=manifest.intended_purpose,
                deployment_context="local",
            )
        )
    )
    return risk.risk_level == RiskLevel.UNACCEPTABLE


def accept_cmd(
    manifest_file: Path = typer.Option(
        Path("system-manifest.json"), "--manifest", "-m", help="System manifest JSON"
    ),
    accepted_by: str = typer.Option(
        ..., "--accepted-by", help="Who is accepting (name or email)"
    ),
    statement: str = typer.Option(
        ..., "--statement", help="Free-text statement, in your own words"
    ),
    repo_root: Path = typer.Option(
        Path("."), "--repo-root", help="Repository root the record is written under"
    ),
    trap_approval: bool = typer.Option(
        False,
        "--trap-approval",
        help="Record an approval of a flagged change instead of a classification "
        "acceptance (needs --change-context)",
    ),
    change_context: str | None = typer.Option(
        None, "--change-context", help="The change being approved (trap approval only)"
    ),
    key: Path | None = typer.Option(
        None,
        "--key",
        help="Private signing key path (default: the key from 'opencomplai init'; "
        "SIGNING_KEY_PRIVATE takes precedence when set)",
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Write a signed acceptance record bound to the manifest, then commit it.

    Exit 0 on success, 2 on invalid input, a missing signing key, or a
    prohibited (Art. 5) system; nothing is written on exit 2.
    """
    main_mod = _main_module()
    record_type = TRAP_APPROVAL if trap_approval else CLASSIFICATION_ACCEPTANCE

    if not accepted_by.strip() or not statement.strip():
        _fail("--accepted-by and --statement must not be empty.")
    if trap_approval and not (change_context and change_context.strip()):
        _fail("--trap-approval needs --change-context.")
    if change_context is not None and not trap_approval:
        _fail("--change-context only applies with --trap-approval.")
    if not manifest_file.exists():
        _fail(f"manifest file not found: {manifest_file}")

    from opencomplai_cli.inputs import load_manifest

    try:
        manifest = load_manifest(manifest_file)
    except Exception as exc:
        _fail(f"manifest validation error: {exc}")

    key_path = key if key is not None else main_mod._SIGNING_KEY
    try:
        public_pem = public_key_pem_from_private(resolve_key(key_path))
    except SigningKeyError as exc:
        _fail(f"{exc}. Run opencomplai init or set SIGNING_KEY_PRIVATE (base64 PEM).")

    if _is_prohibited(manifest):
        _fail(
            "this system is classified as a prohibited practice (Art. 5); "
            "an acceptance cannot apply to it."
        )

    fingerprint = fingerprint_manifest(manifest)
    record = sign_record(
        build_record(
            record_type=record_type,
            system_id=manifest.system_id,
            manifest_fingerprint=fingerprint,
            accepted_by=accepted_by.strip(),
            statement=statement.strip(),
            accepted_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            public_key_pem=public_pem,
            change_context=change_context.strip() if trap_approval else None,
        ),
        key_path,
    )
    path = record_path(repo_root.resolve(), manifest.system_id, record_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    if output == OutputFormat.json:
        main_mod.console.print_json(
            json.dumps(
                {
                    "path": str(path),
                    "record_type": record_type,
                    "key_id": key_id_for(public_pem),
                    "manifest_fingerprint": fingerprint,
                }
            )
        )
    else:
        main_mod.console.print(
            f"Wrote {record_type} record: {path}", soft_wrap=True, markup=False
        )
        main_mod.console.print(
            "Commit this file so `opencomplai check` finds it in the repository.",
            soft_wrap=True,
            markup=False,
        )
