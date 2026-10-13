"""
`scan --propose` and `accept --proposal`: a classification suggested from code,
confirmed by a person.

``write_scan_proposal`` turns the scan's call-site findings into
``classification-proposal.json``. ``confirm_and_record`` shows that proposal to a
person and, only on a yes, writes a signed
``classification_proposal_confirmation`` record. ``check --scan`` reads the confirmed
proposal through ``proposal_gate``; an unconfirmed, edited or stale proposal
changes nothing.

Helpers from `commands/accept.py` and `main` are reached lazily: accept.py
imports this module, so a top-level import would be circular.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from opencomplai_core.acceptance import (
    PROPOSAL_CONFIRMATION,
    build_record,
    key_id_for,
    public_key_pem_from_private,
    record_path,
    sign_record,
)
from opencomplai_core.classification_proposal import (
    PROPOSAL_FILENAME,
    build_proposal_document,
    load_proposal,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.scanner.proposal import build_classification_proposal
from opencomplai_core.signing import SigningKeyError, resolve_key

from opencomplai_cli.commands.halt import OutputFormat


def write_scan_proposal(
    report: Any,
    manifest: Any,
    repo_root: Path,
    *,
    ai_backend: str | None = None,
    ai_model_id: str | None = None,
) -> Path:
    """Write ``repo_root/classification-proposal.json`` for a finished scan."""
    result = build_classification_proposal(report.eu_ai_scan)
    plain = result.model_dump(mode="json")
    area = result.proposed_area_name
    if area is None and result.proposed_annex_iii_area is not None:
        area = f"Annex III area {result.proposed_annex_iii_area}"
    doc = build_proposal_document(
        system_id=manifest.system_id,
        commit_ref=report.commit_ref,
        scanner_version=report.scanner_version,
        scan_input_digest=report.input_digest,
        scan_tree_sha256=report.source_tree_sha256 or None,
        scan_report_hash=report.report_hash,
        manifest_fingerprint=fingerprint_manifest(manifest),
        declared_purpose=manifest.intended_purpose,
        area=area or "none",
        confidence=result.confidence_label,
        evidence=plain["supporting_evidence"],
        minority_evidence=plain["minority_evidence"],
        prohibited_signals=plain["prohibited_signals"],
        proposal=plain,
        ai_backend=ai_backend,
        ai_model_id=ai_model_id,
    )
    path = repo_root / PROPOSAL_FILENAME
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def _print_summary(printer: Any, proposal: dict[str, Any]) -> None:
    def say(text: str) -> None:
        printer.print(text, soft_wrap=True, markup=False)

    def lines(title: str, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        say(f"{title}:")
        for item in items:
            where = item.get("location") or f"{item.get('file')}:{item.get('line')}"
            say(f"  - {where}  {item.get('function', '')}".rstrip())

    say("Classification proposal (suggested from your code):")
    say(f"  area:       {proposal['area']}")
    say(f"  confidence: {proposal['confidence']}")
    lines("Supporting evidence", proposal["evidence"])
    lines("Minority evidence", proposal["minority_evidence"])
    lines("Prohibited-practice signals", proposal["prohibited_signals"])
    for note in proposal["proposal"].get("notes", []):
        say(f"  note: {note}")
    say(proposal["notice"])


def confirm_and_record(
    *,
    proposal_file: Path,
    manifest: Any,
    accepted_by: str,
    statement: str | None,
    repo_root: Path,
    key: Path | None,
    yes: bool,
    output: OutputFormat,
) -> None:
    from opencomplai_cli.commands.accept import _fail, _is_prohibited, _main_module

    main_mod = _main_module()
    try:
        proposal = load_proposal(proposal_file)
    except ValueError as exc:
        _fail(f"invalid proposal: {exc}; run scan --propose again.")
    fingerprint = fingerprint_manifest(manifest)
    if (
        proposal["system_id"] != manifest.system_id
        or proposal["manifest_fingerprint"] != fingerprint
    ):
        _fail(
            "manifest changed since the proposal was written; run scan --propose again."
        )

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

    _print_summary(
        main_mod.err_console if output == OutputFormat.json else main_mod.console,
        proposal,
    )
    if not yes:
        try:
            confirmed = typer.confirm(
                "Confirm this classification proposal?", default=False
            )
        except typer.Abort:
            confirmed = False
        if not confirmed:
            main_mod.err_console.print(
                "Not confirmed; nothing written.", soft_wrap=True, markup=False
            )
            sys.exit(1)

    record = sign_record(
        build_record(
            record_type=PROPOSAL_CONFIRMATION,
            system_id=manifest.system_id,
            manifest_fingerprint=fingerprint,
            accepted_by=accepted_by.strip(),
            statement=(statement or "").strip()
            or f"Confirmed the proposed classification: {proposal['area']}",
            accepted_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            public_key_pem=public_pem,
            proposal_sha256=proposal["proposal_sha256"],
            confirmed_area=proposal["area"],
        ),
        key_path,
    )
    path = record_path(repo_root.resolve(), manifest.system_id, PROPOSAL_CONFIRMATION)
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
                    "record_type": PROPOSAL_CONFIRMATION,
                    "key_id": key_id_for(public_pem),
                    "manifest_fingerprint": fingerprint,
                    "proposal_sha256": record["proposal_sha256"],
                    "confirmed_area": record["confirmed_area"],
                }
            )
        )
    else:
        main_mod.console.print(
            f"Wrote {PROPOSAL_CONFIRMATION} record: {path}",
            soft_wrap=True,
            markup=False,
        )
        main_mod.console.print(
            "This records that a person confirmed the proposal as shown; it is "
            "not a legal classification.",
            soft_wrap=True,
            markup=False,
        )
        main_mod.console.print(
            "Commit this file and the proposal file so the confirmation can be "
            "checked later.",
            soft_wrap=True,
            markup=False,
        )
