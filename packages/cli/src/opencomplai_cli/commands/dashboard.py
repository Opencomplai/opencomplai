"""
CLI dashboard sub-commands (C0.8).

Subcommand: ``opencomplai dashboard enroll``
    Opt an OSS install into the Premium Dashboard.

    1. Validates the bootstrap token against the dashboard
       ``POST /v1/admin/enroll`` (rate-limited, one-time-use).
    2. Registers the install's signing key(s) with the tenant.
    3. Writes an ``EgressConsent`` (``consent_scope=dashboard_metadata``) to
       the OSS-side ledger.
    4. Adds the dashboard endpoint to the local egress-proxy allowlist with a
       per-endpoint policy reference.
    5. Prints the dashboard URL and an audit-event hash the operator can verify.

    Idempotent: re-running with the same tenant returns the existing enrollment
    and emits no new ledger event.

Subcommand: ``opencomplai dashboard withdraw``
    Remove dashboard enrollment for this install.

    Emits a ``consent_revoked`` ledger event and removes the egress-proxy
    allowlist entry within the same command run.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import typer

# Re-use the shared console + config helpers from main via a relative import
# so the dashboard command stays self-contained and testable.
try:
    from rich.console import Console

    _console = Console()
    _err_console = Console(stderr=True)
except ImportError:

    class _FallbackConsole:  # type: ignore[no-redef]
        def print(self, msg: str, **kwargs) -> None:
            builtins_print = (
                __builtins__["print"] if isinstance(__builtins__, dict) else print
            )
            builtins_print(msg)

    _console = _FallbackConsole()  # type: ignore[assignment]
    _err_console = _FallbackConsole()  # type: ignore[assignment]

app = typer.Typer(
    help="Premium Dashboard enrollment and withdrawal.", add_completion=False
)

_OPENCOMPLAI_DIR = Path.home() / ".opencomplai"
_CONFIG_FILE = _OPENCOMPLAI_DIR / "config.yaml"
_SIGNING_PUB = _OPENCOMPLAI_DIR / "signing.pub"
_EGRESS_ALLOWLIST = _OPENCOMPLAI_DIR / "egress_allowlist.json"
_LEDGER_FILE = _OPENCOMPLAI_DIR / "ledger.jsonl"


# ---------------------------------------------------------------------------
# Config I/O (minimal duplication from main.py — dashboard command is
# independently importable for unit testing without pulling in typer).
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    if not _CONFIG_FILE.exists():
        return {}
    try:
        import re

        cfg: dict = {}
        for line in _CONFIG_FILE.read_text().splitlines():
            m = re.match(r"^(\w+):\s*(.+)$", line.strip())
            if m:
                cfg[m.group(1)] = m.group(2).strip()
        return cfg
    except Exception:
        return {}


def _write_config(cfg: dict) -> None:
    _OPENCOMPLAI_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}: {v}" for k, v in cfg.items()]
    _CONFIG_FILE.write_text("\n".join(lines) + "\n")


def _load_egress_allowlist() -> dict:
    if not _EGRESS_ALLOWLIST.exists():
        return {}
    try:
        return json.loads(_EGRESS_ALLOWLIST.read_text())
    except Exception:
        return {}


def _write_egress_allowlist(data: dict) -> None:
    _OPENCOMPLAI_DIR.mkdir(parents=True, exist_ok=True)
    _EGRESS_ALLOWLIST.write_text(json.dumps(data, indent=2) + "\n")


def _append_ledger_event(event: dict) -> None:
    _OPENCOMPLAI_DIR.mkdir(parents=True, exist_ok=True)
    with _LEDGER_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def _ledger_events() -> list[dict]:
    if not _LEDGER_FILE.exists():
        return []
    events: list[dict] = []
    for line in _LEDGER_FILE.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except Exception:
            pass
    return events


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _post(url: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except Exception:
            body = {"error_code": "HTTP_ERROR", "message": str(exc)}
        return exc.code, body
    except Exception as exc:
        raise ConnectionError(f"Dashboard API call failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Enroll command
# ---------------------------------------------------------------------------


@app.command("enroll")
def enroll(
    tenant: str = typer.Option(
        ..., "--tenant", help="Tenant ID from the dashboard signup"
    ),
    token: str = typer.Option(
        ..., "--token", help="One-time bootstrap token from the dashboard"
    ),
    dashboard_url: str = typer.Option(
        "",
        "--dashboard-url",
        help="Dashboard base URL (defaults to OPENCOMPLAI_DASHBOARD_URL env var)",
    ),
) -> None:
    """
    Enroll this install in the Opencomplai Premium Dashboard.

    Validates the bootstrap token, registers signing keys, writes EgressConsent
    to the local ledger, and adds the dashboard endpoint to the egress allowlist.
    """
    cfg = _load_config()
    install_id = cfg.get("install_id", "")
    if not install_id:
        _err_console.print(
            "[red]Error:[/red] install_id not found — run `opencomplai init` first."
        )
        sys.exit(2)

    base_url = dashboard_url.rstrip("/") or os.environ.get(
        "OPENCOMPLAI_DASHBOARD_URL", ""
    ).rstrip("/")
    if not base_url:
        _err_console.print(
            "[red]Error:[/red] dashboard URL not set. "
            "Pass --dashboard-url or set OPENCOMPLAI_DASHBOARD_URL."
        )
        sys.exit(2)

    # --- Idempotency: check if already enrolled ---
    existing = _find_consent_event(tenant, install_id)
    if existing is not None:
        _console.print(
            f"[dim]Already enrolled.[/dim] audit_event_hash={existing.get('audit_event_hash', '?')}"
        )
        _console.print(f"Dashboard: {base_url}")
        return

    # --- Read signing public key ---
    if not _SIGNING_PUB.exists():
        _err_console.print(
            "[red]Error:[/red] signing.pub not found — run `opencomplai init` first."
        )
        sys.exit(2)
    public_key_pem = _SIGNING_PUB.read_text().strip()

    # --- POST /v1/admin/enroll ---
    try:
        status, data = _post(
            f"{base_url}/v1/admin/enroll",
            {
                "tenant_id": tenant,
                "install_id": install_id,
                "bootstrap_token": token,
                "public_key_pem": public_key_pem,
                "consent_scope": "dashboard_metadata",
            },
        )
    except ConnectionError as exc:
        _err_console.print(f"[red]Connection error:[/red] {exc}")
        sys.exit(3)

    if status == 409:
        error_code = data.get("error_code", "")
        if error_code == "TOKEN_CONSUMED":
            _err_console.print(
                "[red]Error:[/red] bootstrap token has already been used (TOKEN_CONSUMED). "
                "Generate a new token from the dashboard."
            )
            sys.exit(3)

    if status >= 400:
        _err_console.print(
            f"[red]Enrollment failed ({status}):[/red] {data.get('message', data)}"
        )
        sys.exit(3)

    audit_event_hash = data.get("audit_event_hash", "")
    dashboard_url_from_api = data.get("dashboard_url", base_url)

    # --- Write EgressConsent ledger event (OSS-side immutable ledger) ---
    from datetime import UTC, datetime

    event = {
        "event_type": "consent_granted",
        "tenant_id": tenant,
        "install_id": install_id,
        "consent_scope": "dashboard_metadata",
        "audit_event_hash": audit_event_hash,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _append_ledger_event(event)

    # --- Add dashboard endpoint to egress allowlist ---
    allowlist = _load_egress_allowlist()
    allowlist[f"dashboard:{tenant}"] = {
        "url": base_url,
        "tenant_id": tenant,
        "policy_ref": "dashboard_metadata_allowlist_v1",
        "consent_scope": "dashboard_metadata",
    }
    _write_egress_allowlist(allowlist)

    _console.print("[green]Enrollment successful.[/green]")
    _console.print(f"  tenant_id:        {tenant}")
    _console.print(f"  install_id:       {install_id}")
    _console.print(f"  audit_event_hash: {audit_event_hash}")
    _console.print(f"\nDashboard: {dashboard_url_from_api}")
    _console.print(
        "\nNext step: run [bold]opencomplai check --sign[/bold] to emit your first signed artifact."
    )


# ---------------------------------------------------------------------------
# Withdraw command
# ---------------------------------------------------------------------------


@app.command("withdraw")
def withdraw(
    tenant: str = typer.Option(..., "--tenant", help="Tenant ID to withdraw from"),
    dashboard_url: str = typer.Option(
        "",
        "--dashboard-url",
        help="Dashboard base URL (defaults to OPENCOMPLAI_DASHBOARD_URL env var)",
    ),
) -> None:
    """
    Withdraw dashboard enrollment for this install.

    Emits a consent_revoked ledger event and removes the egress allowlist entry.
    """
    cfg = _load_config()
    install_id = cfg.get("install_id", "")
    if not install_id:
        _err_console.print(
            "[red]Error:[/red] install_id not found — run `opencomplai init` first."
        )
        sys.exit(2)

    base_url = dashboard_url.rstrip("/") or os.environ.get(
        "OPENCOMPLAI_DASHBOARD_URL", ""
    ).rstrip("/")

    # --- Notify dashboard if URL is available ---
    if base_url:
        try:
            status, data = _post(
                f"{base_url}/v1/admin/withdraw",
                {"tenant_id": tenant, "install_id": install_id},
            )
            if status >= 400:
                _err_console.print(
                    f"[yellow]Warning:[/yellow] dashboard withdraw call returned {status}: "
                    f"{data.get('message', data)}"
                )
        except ConnectionError as exc:
            _err_console.print(
                f"[yellow]Warning:[/yellow] could not reach dashboard: {exc}"
            )

    # --- Emit consent_revoked ledger event ---
    from datetime import UTC, datetime

    event = {
        "event_type": "consent_revoked",
        "tenant_id": tenant,
        "install_id": install_id,
        "consent_scope": "dashboard_metadata",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _append_ledger_event(event)

    # --- Remove egress allowlist entry ---
    allowlist = _load_egress_allowlist()
    key = f"dashboard:{tenant}"
    removed = allowlist.pop(key, None)
    _write_egress_allowlist(allowlist)

    if removed:
        _console.print(
            f"[green]Withdrawal complete.[/green] Egress allowlist entry removed for tenant {tenant}."
        )
    else:
        _console.print(
            f"[dim]No egress allowlist entry found for tenant {tenant} — nothing to remove.[/dim]"
        )
    _console.print("  consent_revoked ledger event written.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_consent_event(tenant_id: str, install_id: str) -> dict | None:
    for ev in _ledger_events():
        if (
            ev.get("event_type") == "consent_granted"
            and ev.get("tenant_id") == tenant_id
            and ev.get("install_id") == install_id
        ):
            # Check not subsequently revoked.
            revoked = any(
                r.get("event_type") == "consent_revoked"
                and r.get("tenant_id") == tenant_id
                and r.get("install_id") == install_id
                for r in _ledger_events()
            )
            if not revoked:
                return ev
    return None


__all__ = ["app"]
