"""
CLI control register command group (CTRL-CLI).

``opencomplai controls`` — the operator surface for Gap A's "missing/stale
evidence" queue: list control instances, assign an owner/TTL, attach
evidence, and print a CI-consumable status line. Every command talks to the
evidence vault's CTRL-STORE endpoints (`GET/PUT /v1/controls`, `POST /v1/
evidence/objects`) — there is no local persistence, so every command requires
``OPENCOMPLAI_VAULT_URL`` to be configured (D11 vault-less OSS mode has no
persistent register to operate on).

Templated on `gaps_cmd` in `opencomplai_cli.main` for the Typer/console/
output-format/exit-code conventions.

Transport helpers (`_vault_request`, `_vault_configured`, `console`,
`err_console`, `__version__`) are obtained LAZILY inside each command via
``from opencomplai_cli import main as _main`` rather than imported at module
load time. `main.py` imports this module's `app` to register the `controls`
sub-typer, so a module-level import back into `main` would be circular; the
lazy import also means tests can monkeypatch
`opencomplai_cli.main._vault_request` exactly as `test_controls_sync.py`
does, since every call looks it up on the module fresh rather than capturing
a stale reference at import time.
"""

from __future__ import annotations

import base64
import json
import sys
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

import typer
from opencomplai_core.control_catalog import get_catalog
from opencomplai_core.control_freshness import (
    FreshnessConfig,
    detect_stale,
    effective_ttl_days,
)
from opencomplai_core.frameworks import EU_AI_ACT, FRAMEWORKS, framework_of
from opencomplai_core.models import ControlInstance, ControlState
from rich.table import Table

app = typer.Typer(
    help="Control register: list, assign owners, attach evidence, CI status."
)


class OutputFormat(StrEnum):
    """CLI output format — mirrors `opencomplai_cli.main.OutputFormat`'s values."""

    human = "human"
    json = "json"


def _require_vault():
    """Lazily fetch the `main` module and enforce D11: every `controls`
    subcommand needs a configured vault, since the register has no
    vault-less local fallback (unlike `gaps`/`check`, where vault sync is an
    optional side effect)."""
    from opencomplai_cli import main as _main

    if not _main._vault_configured():
        _main.err_console.print(
            "[red]Error:[/red] control register requires OPENCOMPLAI_VAULT_URL "
            "(vault-less OSS mode has no persistent register)"
        )
        sys.exit(2)
    return _main


def _list_controls(
    main_mod, system_id: str, state: ControlState | None = None
) -> list[ControlInstance]:
    path = f"/v1/controls/{system_id}"
    if state is not None:
        path += f"?state={state.value}"
    try:
        response = main_mod._vault_request("GET", path)
    except Exception as exc:
        main_mod.err_console.print(f"[red]Error:[/red] vault request failed: {exc}")
        sys.exit(3)
    return [ControlInstance.model_validate(item) for item in response.get("items", [])]


def _fetch_one(main_mod, system_id: str, control_id: str) -> ControlInstance:
    controls = _list_controls(main_mod, system_id)
    for control in controls:
        if control.control_id == control_id:
            return control
    main_mod.err_console.print(
        f"[red]Error:[/red] control {control_id} not found for system {system_id}"
    )
    sys.exit(2)


def _put_patch(main_mod, patch: dict) -> dict:
    try:
        response = main_mod._vault_request("PUT", "/v1/controls", {"items": [patch]})
    except Exception as exc:
        main_mod.err_console.print(f"[red]Error:[/red] vault request failed: {exc}")
        sys.exit(3)
    items = response.get("items", [])
    return items[0] if items else patch


@app.command("list")
def list_cmd(
    system_id: str = typer.Option(..., "--system-id", help="System identifier"),
    state: ControlState | None = typer.Option(
        None, "--state", help="Filter to a single control state"
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """List control instances for a system, with read-time TTL staleness."""
    main_mod = _require_vault()
    controls = _list_controls(main_mod, system_id, state)
    stale_rows = detect_stale(controls, get_catalog())
    stale_ids = {row.control_id for row in stale_rows}

    summary: dict[str, int] = {}
    for control in controls:
        summary[control.state.value] = summary.get(control.state.value, 0) + 1

    if output == OutputFormat.json:
        payload = {
            "system_id": system_id,
            "controls": [
                {
                    **control.model_dump(mode="json"),
                    "stale": control.control_id in stale_ids,
                    "stale_reason": (
                        "ttl_expired" if control.control_id in stale_ids else None
                    ),
                }
                for control in controls
            ],
            "summary": summary,
            "stale_count": len(stale_ids),
        }
        main_mod.console.print_json(json.dumps(payload))
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Control ID", style="dim")
    table.add_column("Article")
    table.add_column("State")
    table.add_column("Owner")
    table.add_column("Due At")
    table.add_column("Stale")
    for control in controls:
        table.add_row(
            control.control_id[:12],
            control.article_ref,
            control.state.value,
            control.owner or "—",
            control.due_at or "—",
            "yes (ttl_expired)" if control.control_id in stale_ids else "—",
        )
    main_mod.console.print(table)
    counts = " · ".join(
        f"{count} {state_name}" for state_name, count in sorted(summary.items())
    )
    main_mod.console.print(
        f"\n[dim]{len(controls)} controls"
        + (f" — {counts}" if counts else "")
        + f" · {len(stale_ids)} stale-by-ttl[/dim]"
    )


@app.command("assign")
def assign_cmd(
    control_id: str = typer.Argument(..., help="Control instance id"),
    system_id: str = typer.Option(..., "--system-id", help="System identifier"),
    owner: str = typer.Option(..., "--owner", help="Accountable owner email"),
    ttl_days: int | None = typer.Option(
        None, "--ttl-days", help="Per-control evidence freshness TTL override"
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Assign an owner (and optionally a TTL override) to a control instance."""
    main_mod = _require_vault()
    control = _fetch_one(main_mod, system_id, control_id)

    patch: dict = {"control_id": control_id, "owner": owner}
    if ttl_days is not None:
        patch["ttl_days"] = ttl_days
    updated = _put_patch(main_mod, patch)

    if output == OutputFormat.json:
        main_mod.console.print_json(json.dumps(updated))
        return

    ttl_note = f" (ttl {ttl_days}d)" if ttl_days is not None else ""
    main_mod.console.print(
        f"[dim]Assigned {control_id[:12]} ({control.article_ref}) to {owner}{ttl_note}[/dim]"
    )


@app.command("attach-evidence")
def attach_evidence_cmd(
    control_id: str = typer.Argument(..., help="Control instance id"),
    path: Path = typer.Argument(..., help="Path to the evidence file"),
    system_id: str = typer.Option(..., "--system-id", help="System identifier"),
    source: str = typer.Option(
        "opencomplai-cli", "--source", help="Identity of the collecting tool"
    ),
    source_version: str | None = typer.Option(
        None, "--source-version", help="Version of the collecting tool"
    ),
    valid_until: str | None = typer.Option(
        None,
        "--valid-until",
        help="ISO-8601 timestamp after which this evidence is stale",
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Store a file as evidence (CAS + EVID-PROV metadata), bind its hash to
    the control, and re-evaluate the control's state."""
    main_mod = _require_vault()

    if not path.exists():
        main_mod.err_console.print(f"[red]Error:[/red] evidence file not found: {path}")
        sys.exit(2)

    control = _fetch_one(main_mod, system_id, control_id)
    content = path.read_bytes()
    collected_at = datetime.now(UTC).isoformat()
    resolved_source_version = (
        source_version if source_version is not None else main_mod.__version__
    )

    evidence_body: dict = {
        "content_base64": base64.b64encode(content).decode("utf-8"),
        "source": source,
        "source_version": resolved_source_version,
        "collected_at": collected_at,
    }
    if valid_until is not None:
        evidence_body["valid_until"] = valid_until

    try:
        evidence_response = main_mod._vault_request(
            "POST", "/v1/evidence/objects", evidence_body
        )
    except Exception as exc:
        main_mod.err_console.print(f"[red]Error:[/red] vault request failed: {exc}")
        sys.exit(3)

    content_hash = evidence_response["content_hash"]

    evidence_refs = list(control.evidence_refs)
    if content_hash not in evidence_refs:
        evidence_refs.append(content_hash)

    ttl_days = effective_ttl_days(control, get_catalog(), FreshnessConfig())
    due_at = None
    if ttl_days is not None:
        due_at = (
            datetime.fromisoformat(collected_at) + timedelta(days=ttl_days)
        ).isoformat()
    if valid_until is not None and (due_at is None or valid_until < due_at):
        due_at = valid_until

    patch: dict = {
        "control_id": control_id,
        "evidence_refs": evidence_refs,
        "last_evidence_at": collected_at,
        "due_at": due_at,
    }
    if control.state == ControlState.WAIVED:
        new_state = ControlState.WAIVED
    else:
        new_state = ControlState.SATISFIED
        patch["state"] = new_state.value
    _put_patch(main_mod, patch)

    if output == OutputFormat.json:
        main_mod.console.print_json(json.dumps({**patch, "content_hash": content_hash}))
        return

    main_mod.console.print(
        f"[dim]Attached {content_hash[:19]}… to {control_id[:12]} "
        f"({control.article_ref}) — state {new_state.value}, "
        f"due {due_at or '—'}[/dim]"
    )


@app.command("status")
def status_cmd(
    system_id: str = typer.Option(..., "--system-id", help="System identifier"),
    fail_on_missing: bool = typer.Option(
        True,
        "--fail-on-missing/--no-fail-on-missing",
        help="Gate exit code 1 on evidence_missing controls too (default: on)",
    ),
    framework: list[str] | None = typer.Option(
        None,
        "--framework",
        help=(
            "Count only this framework's controls; repeat for several "
            "(default: EU_AI_ACT plus the frameworks opencomplai.yaml gates)"
        ),
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """One-line control register summary; exit 1 when any control is
    missing/stale evidence or pending review (CI-consumable)."""
    main_mod = _require_vault()
    frameworks = framework or [
        EU_AI_ACT,
        *main_mod._project_config(Path(".")).gate_frameworks,
    ]
    unknown = [fw for fw in frameworks if fw not in FRAMEWORKS]
    if unknown:
        main_mod.err_console.print(
            f"[red]Error:[/red] unknown framework {', '.join(unknown)}; known "
            f"frameworks: {', '.join(FRAMEWORKS)}"
        )
        sys.exit(2)
    controls = [
        control
        for control in _list_controls(main_mod, system_id)
        if framework_of(control.obligation_id) in frameworks
    ]
    stale_rows = detect_stale(controls, get_catalog())
    stale_count = len(stale_rows)

    summary: dict[str, int] = {}
    for control in controls:
        summary[control.state.value] = summary.get(control.state.value, 0) + 1

    satisfied = summary.get(ControlState.SATISFIED.value, 0)
    missing = summary.get(ControlState.EVIDENCE_MISSING.value, 0)
    stale_state = summary.get(ControlState.EVIDENCE_STALE.value, 0)
    pending = summary.get(ControlState.PENDING_REVIEW.value, 0)
    waived = summary.get(ControlState.WAIVED.value, 0)

    has_gate_issue = stale_state > 0 or pending > 0 or stale_count > 0
    if fail_on_missing:
        has_gate_issue = has_gate_issue or missing > 0
    exit_code = 1 if has_gate_issue else 0

    if output == OutputFormat.json:
        payload = {
            "system_id": system_id,
            "summary": summary,
            "stale_count": stale_count,
            "exit_code": exit_code,
        }
        main_mod.console.print_json(json.dumps(payload))
        sys.exit(exit_code)

    line = (
        f"controls: {len(controls)} total · {satisfied} satisfied · "
        f"{missing} evidence_missing · {stale_state} evidence_stale · "
        f"{pending} pending_review · {waived} waived · "
        f"{stale_count} stale-by-ttl"
    )
    main_mod.console.print(line)
    sys.exit(exit_code)
