"""
CLI halt/resume commands (HALT-WIRE).

`opencomplai approve` mints a signed HITL approval token for a system that
`opencomplai check` has put into HALTED_PENDING_REVIEW; `opencomplai resume`
verifies that token and drives the existing `state_machine.transition()`
gate back to RUNNING. Both are registered as top-level `opencomplai`
commands (not a sub-typer) — `main.py` imports `approve_cmd`/`resume_cmd`
from here and registers them with `app.command(...)`.

Transport helpers (`console`, `err_console`, `_emit_event`, `_state_dir`,
`_SIGNING_KEY`, `_SIGNING_PUB`) are obtained LAZILY inside each command via
``from opencomplai_cli import main as _main`` rather than imported at module
load time — templated on `commands/controls.py`'s docstring: `main.py` must
import this module to register `approve`/`resume`, so a module-level import
back into `main` here would be circular.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import typer
from opencomplai_core.models import SystemState
from opencomplai_core.signing import (
    SigningDomain,
    sign_bundle_bytes,
    verify_bundle_bytes,
)
from opencomplai_core.state_machine import APPROVAL_GRANTED_EVENT, transition
from opencomplai_core.system_state_store import load_state, save_state, state_record


class OutputFormat(StrEnum):
    """CLI output format — mirrors `opencomplai_cli.main.OutputFormat`'s values."""

    human = "human"
    json = "json"


def _main_module():
    from opencomplai_cli import main as _main

    return _main


def _mint_token(
    *,
    system_id: str,
    commit_ref: str,
    halted_at: str,
    approver: str,
    key_path: Path,
    role: str | None = None,
) -> tuple[str, dict]:
    """`base64(json payload) + "." + signature_b64`, signed over the JSON
    payload bytes under `SigningDomain.APPROVAL_TOKEN` — see
    `opencomplai_core.signing.sign_bundle_bytes`."""
    payload = {
        "system_id": system_id,
        "commit_ref": commit_ref,
        "halted_at": halted_at,
        "approver": approver,
        "issued_at": datetime.now(UTC).isoformat(),
    }
    if role is not None:
        payload["role"] = role
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature_b64 = sign_bundle_bytes(
        payload_bytes, key_path, SigningDomain.APPROVAL_TOKEN
    )
    payload_b64 = base64.b64encode(payload_bytes).decode("ascii")
    return f"{payload_b64}.{signature_b64}", payload


def _parse_token(token_str: str) -> tuple[dict, bytes, str] | None:
    payload_b64, sep, signature_b64 = token_str.partition(".")
    if not sep or not signature_b64:
        return None
    try:
        payload_bytes = base64.b64decode(payload_b64)
        payload = json.loads(payload_bytes)
    except Exception:
        return None
    return payload, payload_bytes, signature_b64


def approve_cmd(
    system_id: str = typer.Option(..., "--system-id", help="System identifier"),
    approver: str = typer.Option(
        ..., "--approver", help="Approver identity (e.g. email) bound into the token"
    ),
    key: Path | None = typer.Option(
        None,
        "--key",
        help="Private signing key path (defaults to the local signing key from "
        "'opencomplai init'/'opencomplai keys rotate')",
    ),
    role: str | None = typer.Option(
        None,
        "--role",
        help="Approver's oversight role; must be one the manifest declares "
        "(required when it declares any)",
    ),
    manifest: Path = typer.Option(
        Path("system-manifest.json"),
        "--manifest",
        help="Manifest whose human_oversight roles are checked (a missing file is fine)",
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Mint a signed HITL approval token for a HALTED_PENDING_REVIEW system.

    Refuses (exit 2) if the system is not currently HALTED_PENDING_REVIEW —
    there is nothing to approve. The token's `halted_at` is taken from the
    persisted halt record, binding the token to *this* halt rather than any
    future one.
    """
    main_mod = _main_module()
    state_dir = main_mod._state_dir()
    current_state = load_state(state_dir, system_id)
    record = state_record(state_dir, system_id)

    if current_state != SystemState.HALTED_PENDING_REVIEW or record is None:
        main_mod.err_console.print(
            f"[red]Error:[/red] system {system_id} is not HALTED_PENDING_REVIEW "
            f"(current state: {current_state.value}) — nothing to approve."
        )
        sys.exit(2)

    from opencomplai_cli.check_signing import signing_key_available

    key_path = key if key is not None else main_mod._SIGNING_KEY
    # An explicit --key beats the environment; the default may use SIGNING_KEY_PRIVATE.
    if not (key_path.exists() if key is not None else signing_key_available(key_path)):
        main_mod.err_console.print(
            f"[red]Error:[/red] signing key not found: {key_path}"
        )
        sys.exit(2)

    from opencomplai_cli.commands import oversight_log

    try:
        role, role_declared = oversight_log.resolve_role(manifest, role)
    except ValueError as exc:
        main_mod.err_console.print(f"Error: {exc}", markup=False)
        sys.exit(2)

    token, payload = _mint_token(
        system_id=system_id,
        commit_ref=record.get("commit_ref", ""),
        halted_at=record["changed_at"],
        approver=approver,
        key_path=key_path,
        role=role,
    )
    try:
        oversight_log.append_entry(
            {
                "event": "approval_minted",
                "system_id": system_id,
                "approver": approver,
                "role": role,
                "role_declared": role_declared,
                "halted_at": payload["halted_at"],
                "commit_ref": payload["commit_ref"],
            },
            key_path,
        )
    except OSError as exc:
        main_mod.err_console.print(
            f"Error: cannot write the oversight log: {exc}", markup=False
        )
        sys.exit(2)

    if output == OutputFormat.json:
        main_mod.console.print_json(json.dumps({"token": token, **payload}))
    else:
        main_mod.console.print("\n[bold green]Approval token minted[/bold green]")
        main_mod.console.print(f"  system_id:   {system_id}")
        main_mod.console.print(f"  halted_at:   {payload['halted_at']}")
        main_mod.console.print(f"  approver:    {approver}")
        if role is not None:
            main_mod.console.print(f"  role:        {role}", markup=False)
        main_mod.console.print(f"\n  {token}\n")


def resume_cmd(
    system_id: str = typer.Option(..., "--system-id", help="System identifier"),
    approval_token: str = typer.Option(
        ...,
        "--approval-token",
        help="Token from 'opencomplai approve', or '@path/to/token-file'",
    ),
    pub_key: Path | None = typer.Option(
        None,
        "--pub-key",
        help="Public signing key path (defaults to the local signing key from "
        "'opencomplai init'/'opencomplai keys rotate')",
    ),
    key: Path | None = typer.Option(
        None,
        "--key",
        help="Private key used only to sign the oversight log entry (defaults to "
        "the local signing key; the entry is written unsigned when none resolves)",
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Resume a HALTED_PENDING_REVIEW system with a signed approval token.

    Verifies the token's signature (`SigningDomain.APPROVAL_TOKEN`), that it
    names this `system_id`, and that its `halted_at` matches the persisted
    halt record — a token minted for an earlier halt of the same system does
    not resume a later one. An invalid/mismatched token exits 2 and leaves
    the state unchanged; a system that is not halted exits 0 with a note.
    """
    main_mod = _main_module()
    state_dir = main_mod._state_dir()
    current_state = load_state(state_dir, system_id)

    if current_state != SystemState.HALTED_PENDING_REVIEW:
        main_mod.console.print(
            f"[dim]System {system_id} is not HALTED_PENDING_REVIEW "
            f"(current state: {current_state.value}) — nothing to resume.[/dim]"
        )
        sys.exit(0)

    token_str = approval_token
    if token_str.startswith("@"):
        token_path = Path(token_str[1:])
        try:
            token_str = token_path.read_text().strip()
        except OSError as exc:
            main_mod.err_console.print(
                f"[red]Error:[/red] cannot read approval token file: {exc}"
            )
            sys.exit(2)

    parsed = _parse_token(token_str)
    pub_key_path = pub_key if pub_key is not None else main_mod._SIGNING_PUB
    record = state_record(state_dir, system_id)

    valid = False
    payload: dict = {}
    if parsed is not None and pub_key_path.exists() and record is not None:
        payload, payload_bytes, signature_b64 = parsed
        valid = (
            verify_bundle_bytes(
                payload_bytes, signature_b64, pub_key_path, SigningDomain.APPROVAL_TOKEN
            )
            and payload.get("system_id") == system_id
            and payload.get("halted_at") == record.get("changed_at")
        )

    if not valid:
        main_mod.err_console.print(
            f"[red]Error:[/red] approval token is invalid, tampered, or does not "
            f"match the current halt for system {system_id}."
        )
        sys.exit(2)

    result = transition(
        SystemState.HALTED_PENDING_REVIEW,
        APPROVAL_GRANTED_EVENT,
        has_approval_token=True,
    )
    if not result.success:
        main_mod.err_console.print(f"[red]Error:[/red] {result.error}")
        sys.exit(2)

    approver = payload.get("approver", "unknown")
    role = payload.get("role")
    from opencomplai_core.signing import SigningKeyError, resolve_key

    from opencomplai_cli.commands import oversight_log

    log_key = key if key is not None else main_mod._SIGNING_KEY
    try:
        resolve_key(log_key)
    except SigningKeyError:
        main_mod.err_console.print(
            "oversight log entry written unsigned: no signing key", markup=False
        )
    try:
        oversight_log.append_entry(
            {
                "event": "resume_granted",
                "system_id": system_id,
                "approver": approver,
                "role": role,
                "role_declared": bool(role),
                "halted_at": payload.get("halted_at"),
                "commit_ref": payload.get("commit_ref", ""),
                "token_sha256": hashlib.sha256(token_str.encode("utf-8")).hexdigest(),
            },
            log_key,
        )
    except OSError as exc:
        main_mod.err_console.print(
            f"Error: cannot write the oversight log: {exc}", markup=False
        )
        sys.exit(2)

    save_state(
        state_dir,
        system_id,
        result.new_state,
        reason=f"approved by {approver}",
        commit_ref=payload.get("commit_ref", ""),
    )
    main_mod._emit_event(
        "approval_granted",
        {
            "system_id": system_id,
            "approver": approver,
            "commit_ref": payload.get("commit_ref", ""),
        },
    )

    if output == OutputFormat.json:
        main_mod.console.print_json(
            json.dumps({"system_id": system_id, "state": result.new_state.value})
        )
    else:
        main_mod.console.print(
            f"[bold green]System {system_id} resumed to RUNNING[/bold green] "
            f"(approved by {approver}{f', role {role}' if role else ''})."
        )
