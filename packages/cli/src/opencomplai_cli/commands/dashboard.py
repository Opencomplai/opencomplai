"""
CLI dashboard sub-commands (C0.8).

Subcommand: ``opencomplai dashboard enroll`` (hidden — see its own docstring)
    Opt an OSS install into the Premium Dashboard via a one-time bootstrap
    token. This is an operator path: the token has to come from somewhere,
    and as of DG-11 nothing in this repo issues one outside a test (admin-api's
    ``issue_bootstrap_token`` has zero non-test callers — no route, no web UI).
    The self-serve onboarding path is the ``/connect`` page + an
    ``OPENCOMPLAI_API_KEY`` (see ``opencomplai push`` / ``opencomplai docs
    generate --push``), which needs none of this.

Subcommand: ``opencomplai dashboard withdraw``
    Clear this install's local enrollment state (egress-allowlist entry +
    a ``consent_revoked`` ledger event) unconditionally. Also best-effort
    notifies the dashboard's ``POST /v1/admin/withdraw`` when this install
    can actually authenticate to it — that endpoint requires a tenant-scoped
    service JWT (SEC-2) that a plain OSS install typically never has (it is
    minted from ``enroll``'s OIDC client-credentials pair, and ``enroll`` is
    the hidden/effectively-dead path described above). When no such token
    can be produced, the remote call is skipped rather than sent bare and
    guaranteed a 401 — see ``withdraw()``'s own docstring.
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

app = typer.Typer(help="Premium Dashboard connection management.", add_completion=False)

_OPENCOMPLAI_DIR = Path.home() / ".opencomplai"
_CONFIG_FILE = _OPENCOMPLAI_DIR / "config.yaml"
_SIGNING_PUB = _OPENCOMPLAI_DIR / "signing.pub"
_EGRESS_ALLOWLIST = _OPENCOMPLAI_DIR / "egress_allowlist.json"
_LEDGER_FILE = _OPENCOMPLAI_DIR / "ledger.jsonl"
_CLIENT_SECRET_FILE = _OPENCOMPLAI_DIR / "client.secret"


def _write_client_secret(raw_secret: str) -> None:
    """
    Persist the plaintext client_secret received once from /enroll. Stored
    as a dedicated file (mirroring signing.key/signing.pub's separateness
    from config.yaml's non-secret flat scalars), chmod 0600 where the
    platform supports it — a no-op on Windows, where this permission model
    doesn't apply the same way.
    """
    _OPENCOMPLAI_DIR.mkdir(parents=True, exist_ok=True)
    _CLIENT_SECRET_FILE.write_text(raw_secret)
    try:
        os.chmod(_CLIENT_SECRET_FILE, 0o600)
    except (OSError, NotImplementedError):
        pass


def _read_client_secret() -> str | None:
    if not _CLIENT_SECRET_FILE.exists():
        return None
    secret = _CLIENT_SECRET_FILE.read_text().strip()
    return secret or None


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


@app.command("enroll", hidden=True)
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
    Operator path pending a UI to mint bootstrap tokens.

    Enrolls this install in the Opencomplai Premium Dashboard by validating a
    one-time bootstrap token, registering signing keys, writing EgressConsent
    to the local ledger, and adding the dashboard endpoint to the egress
    allowlist. Hidden from --help as of DG-11: nothing in this product issues
    a bootstrap token outside a test today (admin-api's
    ``issue_bootstrap_token`` has zero non-test callers), so this command has
    no working entry point for a real customer to reach. It is kept, not
    deleted, for the operator who already has -- or will eventually get a
    console to mint -- a token. Everyone else wants the self-serve path:
    an API key from ``/connect`` plus ``opencomplai push`` /
    ``opencomplai docs generate --push``.
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

    # --- Persist OIDC client-credentials pair (AUTH-SAAS) ---
    # /enroll is the only place these are ever returned; client_id is not
    # secret (like install_id) and lives in config.yaml, client_secret gets
    # its own file since it must never be handed back a second time.
    client_id = data.get("client_id", "")
    client_secret = data.get("client_secret", "")
    if client_id and client_secret:
        cfg["client_id"] = client_id
        _write_config(cfg)
        _write_client_secret(client_secret)

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
    if client_id and client_secret:
        _console.print(f"  client_id:        {client_id}")
        _console.print(f"  client_secret:    saved to {_CLIENT_SECRET_FILE}")
    _console.print(f"\nDashboard: {dashboard_url_from_api}")
    _console.print(
        "\nNext step: run [bold]opencomplai check --sign[/bold] to emit your first signed artifact."
    )


# ---------------------------------------------------------------------------
# Withdraw command
# ---------------------------------------------------------------------------


def _resolve_withdraw_token() -> str | None:
    """
    Best-effort bearer token for admin-api's ``POST /v1/admin/withdraw``
    (SEC-2's ``PrincipalDep`` requires a tenant-scoped service JWT), mirroring
    the CI connectors' own auth precedence
    (``connectors/github_actions.py``/``gitlab_ci.py``): an operator-set
    legacy bearer-token env var wins outright; otherwise this install's own
    OIDC client-credentials pair (persisted locally by ``enroll`` — see
    module docstring) is exchanged for a short-lived JWT.

    Returns ``None`` — never raises — when neither path produces a token.
    That is the *ordinary* outcome for the vast majority of installs, which
    never went through ``enroll`` (it is hidden and has no working entry
    point today): callers must treat it as "there is nothing to
    authenticate a remote withdraw with," not as an error.
    """
    token = os.environ.get("OPENCOMPLAI_AUTH_TOKEN", "")
    if token:
        return token

    client_id = _load_config().get("client_id", "")
    client_secret = _read_client_secret() or ""
    token_endpoint = os.environ.get("OPENCOMPLAI_TOKEN_ENDPOINT", "")
    if not (client_id and client_secret and token_endpoint):
        return None

    from opencomplai_cli.oidc_client import OidcTokenError, acquire_token

    try:
        token, _ = acquire_token(token_endpoint, client_id, client_secret)
    except OidcTokenError:
        return None
    return token


@app.command("withdraw")
def withdraw(
    tenant: str = typer.Option(..., "--tenant", help="Tenant ID to withdraw from"),
    dashboard_url: str = typer.Option(
        "",
        "--dashboard-url",
        help="Dashboard base URL (defaults to OPENCOMPLAI_DASHBOARD_URL env var)",
    ),
    local_only: bool = typer.Option(
        False,
        "--local-only",
        help=(
            "Clear local state only — never attempt the remote "
            "/v1/admin/withdraw call, even if a token is available."
        ),
    ),
) -> None:
    """
    Withdraw dashboard enrollment for this install.

    Always clears local state: emits a consent_revoked ledger event and
    removes the egress allowlist entry, in this same run. Also best-effort
    notifies the dashboard, but only when a bearer token can actually be
    produced for it (see _resolve_withdraw_token) — admin-api's
    /v1/admin/withdraw requires an authenticated, tenant-scoped service JWT
    (SEC-2), which most OSS installs have no way to mint. Sending the
    request anyway would just guarantee a 401 that looks like a real
    failure; skipping it prints a direct next step instead. A genuine
    >=400 from the dashboard on a request that *did* carry a token is a
    real rejection and still gets the loud error message.
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

    # --- Notify dashboard, only if we can actually authenticate to it ---
    # Best-effort and non-fatal by design (an offline install can still clear
    # its own local state). Three distinct outcomes below, each with its own
    # message: (1) skipped because no token could be minted, or --local-only
    # was passed, or no dashboard URL is configured at all -- the common
    # case, not an error; (2) skipped because of an actual bug/note aside;
    # (3) attempted with a real token and the dashboard rejected it (>=400)
    # or was unreachable -- a genuine failure, kept loud so it isn't
    # confused with (1)'s "there was never anything to try" case.
    dashboard_notified = False
    skipped_no_token = True
    if base_url and not local_only:
        token = _resolve_withdraw_token()
        if token is not None:
            skipped_no_token = False
            try:
                status, data = _post(
                    f"{base_url}/v1/admin/withdraw",
                    {"tenant_id": tenant, "install_id": install_id},
                    token=token,
                )
                if status >= 400:
                    _err_console.print(
                        f"[red]Error:[/red] dashboard rejected the withdraw request "
                        f"({status}: {data.get('message', data)}) — egress consent was "
                        "NOT revoked server-side. Clearing local state only."
                    )
                else:
                    dashboard_notified = True
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

    if dashboard_notified:
        if removed:
            _console.print(
                f"[green]Withdrawal complete.[/green] Egress allowlist entry removed for tenant {tenant}."
            )
        else:
            _console.print(
                f"[green]Withdrawal complete.[/green] No local egress allowlist entry was present for tenant {tenant}."
            )
    elif skipped_no_token:
        _console.print(
            "[green]Local state cleared.[/green] Remote egress consent must be "
            "revoked from the dashboard (Projects → Archive project)."
        )
    elif removed:
        _console.print(
            f"[yellow]Local withdrawal complete[/yellow] — egress allowlist entry removed "
            f"for tenant {tenant}, but the dashboard was not notified (see error above). "
            "Server-side egress consent likely remains active."
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
