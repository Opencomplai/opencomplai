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
    ART_6_3_EXEMPTION,
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
from opencomplai_core.models import (
    ART_6_3_GROUND_IDS,
    AssessmentInput,
    ModelMetadata,
    RiskLevel,
)
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
    statement: str | None = typer.Option(
        None,
        "--statement",
        help="Free-text statement, in your own words (required unless --proposal)",
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
    exemption: bool = typer.Option(
        False,
        "--exemption",
        help="Record a declaration that an Annex III system relies on the Art. 6(3) "
        "exceptions (a declaration, not a legal finding; needs legal review)",
    ),
    ground: list[str] | None = typer.Option(
        None,
        "--ground",
        help="Art. 6(3) ground relied on, repeatable (exemption only): hr3_art_6_3, "
        "hr4_narrow_task, hr5_no_significant_risk or hr6_accessory. Default: the "
        "manifest's checker_session.derogation_grounds",
    ),
    proposal: Path | None = typer.Option(
        None,
        "--proposal",
        help="Confirm a classification-proposal.json written by 'scan --propose' "
        "(a suggestion from your code; you confirm it)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Confirm without the prompt (only with --proposal)",
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
    prohibited (Art. 5) system; nothing is written on exit 2. With
    ``--proposal``, exit 1 when the person does not confirm; nothing is written.
    """
    main_mod = _main_module()
    if trap_approval:
        record_type = TRAP_APPROVAL
    elif exemption:
        record_type = ART_6_3_EXEMPTION
    else:
        record_type = CLASSIFICATION_ACCEPTANCE

    if proposal is None and yes:
        _fail("--yes only applies with --proposal.")
    if proposal is not None and (trap_approval or exemption or change_context):
        _fail(
            "--proposal cannot be combined with --trap-approval, --exemption "
            "or --change-context."
        )
    if not accepted_by.strip() or (
        proposal is None and not (statement and statement.strip())
    ):
        _fail("--accepted-by and --statement must not be empty.")
    if exemption and trap_approval:
        _fail("--exemption and --trap-approval cannot be combined.")
    if ground and not exemption:
        _fail("--ground only applies with --exemption.")
    unknown = [g for g in ground or [] if g not in ART_6_3_GROUND_IDS]
    if unknown:
        _fail(
            f"unknown --ground {', '.join(unknown)}; "
            f"use one of: {', '.join(ART_6_3_GROUND_IDS)}."
        )
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

    if proposal is not None:
        from opencomplai_cli.commands.proposal import confirm_and_record

        confirm_and_record(
            proposal_file=proposal,
            manifest=manifest,
            accepted_by=accepted_by,
            statement=statement,
            repo_root=repo_root,
            key=key,
            yes=yes,
            output=output,
        )
        return

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

    grounds: list[str] | None = None
    if exemption:
        cs = manifest.checker_session
        grounds = list(ground) if ground else list(cs.derogation_grounds if cs else [])
        if not grounds:
            _fail(
                "an exemption needs --ground (one or more of: "
                f"{', '.join(ART_6_3_GROUND_IDS)}); the manifest's checker session "
                "has no derogation_grounds to default from."
            )

    fingerprint = fingerprint_manifest(manifest)
    record = sign_record(
        build_record(
            record_type=record_type,
            system_id=manifest.system_id,
            manifest_fingerprint=fingerprint,
            accepted_by=accepted_by.strip(),
            statement=(statement or "").strip(),
            accepted_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            public_key_pem=public_pem,
            change_context=change_context.strip() if trap_approval else None,
            grounds=grounds,
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
        payload = {
            "path": str(path),
            "record_type": record_type,
            "key_id": key_id_for(public_pem),
            "manifest_fingerprint": fingerprint,
        }
        if grounds is not None:
            payload["grounds"] = record["grounds"]
        main_mod.console.print_json(json.dumps(payload))
    else:
        main_mod.console.print(
            f"Wrote {record_type} record: {path}", soft_wrap=True, markup=False
        )
        if grounds is not None:
            main_mod.console.print(
                "This record is a declaration by a person, not a legal finding; "
                "it needs legal review.",
                soft_wrap=True,
                markup=False,
            )
        main_mod.console.print(
            "Commit this file so `opencomplai check` finds it in the repository.",
            soft_wrap=True,
            markup=False,
        )
