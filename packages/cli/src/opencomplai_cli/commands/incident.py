"""CLI incident command group: declare, classify, notify, close, status, export, template.

Operates on a local current-state JSON register (default ``incident-register.json``).
Every change is also appended to a signed, hash-chained incident log file (structured
fields only, never the free text). ``declare`` and ``close`` write that entry first, then
drive the system state machine. Deadlines are provisional data pending founder and lawyer
review.

``console`` / ``err_console`` come from ``opencomplai_cli.main`` lazily inside each
command: ``main`` imports this module to register the group, so a module-level
import back into ``main`` would be circular (same pattern as ``commands/controls.py``).
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import typer
from opencomplai_core import incident as inc
from opencomplai_core import incident_log as ilog
from opencomplai_core import incident_templates as itpl
from opencomplai_core.gap_probes import INCIDENT_LOG_PATH
from opencomplai_core.incident import IncidentClass, IncidentContact, PartyKind
from opencomplai_core.signed_log import verify_log
from opencomplai_core.signing import SigningDomain, SigningKeyError, resolve_key
from rich.markup import escape

from opencomplai_cli.commands.verify import (
    EMPTY_LOG,
    LOG_EXPECT_KEYS,
    VerifyInputError,
    VerifyResult,
    log_anchor,
    log_error,
    register_kind,
)

app = typer.Typer(
    help=(
        "Incident records (Art. 73): declare, classify, notify, close, status, export. "
        "Deadlines are provisional, pending founder/lawyer review."
    )
)


class OutputFormat(StrEnum):
    human = "human"
    json = "json"


class ExportFormat(StrEnum):
    md = "md"
    json = "json"


class TemplateKind(StrEnum):
    authority = "authority"
    downstream = "downstream"


_FILE = typer.Option(
    Path("incident-register.json"), "--file", "-f", help="Incident register file"
)
_LOG = typer.Option(
    None,
    "--log",
    help="Signed incident log (default: the standard log file name, beside --file)",
)
_KEY = typer.Option(
    None, "--key", help="Private signing key (default: ~/.opencomplai/signing.key)"
)
_COMMIT_REF = typer.Option("HEAD", "--commit-ref", help="Recorded with a state change")
_MANIFEST = typer.Option(
    Path("system-manifest.json"),
    "--manifest",
    help="System manifest (system id, contacts)",
)


def _now() -> datetime:
    # The only wall-clock read in this epic's CLI code; tests set OPENCOMPLAI_NOW.
    fixed = os.environ.get("OPENCOMPLAI_NOW")
    return inc.parse_ts(fixed) if fixed else datetime.now(UTC)


def _err(msg: str) -> None:
    from opencomplai_cli import main as _main

    _main.err_console.print(f"[red]Error:[/red] {escape(msg)}")


@contextmanager
def _guard():
    """Turn any ValueError into exit 2; callers save only after the block passes."""
    try:
        yield
    except ValueError as exc:
        _err(str(exc))
        sys.exit(2)


def _log_ctx(log: Path | None, file: Path, key: Path | None):
    """Log path plus private key PEM (None, with one warning, means an unsigned entry)."""
    from opencomplai_cli import main as _main

    try:
        pem = resolve_key(key or _main._SIGNING_KEY)
    except SigningKeyError as exc:
        _main.err_console.print(
            f"[yellow]Warning:[/yellow] {escape(str(exc))}; log entry is unsigned"
        )
        pem = None
    return log or file.parent / INCIDENT_LOG_PATH, pem


def _write_log(event, payload, log, file, key):
    """Append one entry without a state change. A log OSError becomes exit 2 via _guard."""
    path, pem = _log_ctx(log, file, key)
    try:
        ilog.append_event(path, event, payload, ts=inc.fmt_ts(_now()), private_pem=pem)
    except OSError as exc:
        raise ValueError(f"cannot write incident log: {exc.strerror or exc}") from None


def _drive(event, rec, payload, log, file, key, commit_ref):
    """Log first, then drive the state machine. A log OSError becomes exit 2 via _guard."""
    from opencomplai_cli import main as _main

    path, pem = _log_ctx(log, file, key)
    try:
        return ilog.log_then_transition(
            state_dir=_main._state_dir(),
            log_path=path,
            system_id=rec.system_id,
            event=event,
            payload=payload,
            ts=inc.fmt_ts(_now()),
            commit_ref=commit_ref,
            private_pem=pem,
        )
    except OSError as exc:
        raise ValueError(f"cannot write incident log: {exc.strerror or exc}") from None


def _finish(out) -> None:
    """A refused transition keeps its log entries; report it and exit 1."""
    if not out.transitioned:
        _err(out.error or "state transition refused")
        sys.exit(1)


def _read_manifest(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_bytes())
        if not isinstance(data, dict):
            raise ValueError("manifest is not a JSON object")
        return data
    except ValueError as exc:
        from opencomplai_cli import main as _main

        _main.err_console.print(
            f"[yellow]Warning:[/yellow] manifest {escape(str(path))} unreadable: {escape(str(exc))}"
        )
        return None


def _contacts(manifest: Path) -> list[IncidentContact]:
    data = _read_manifest(manifest)
    if data is None:
        return []
    try:
        return [
            IncidentContact.model_validate(c) for c in data.get("incident_contacts", [])
        ]
    except (ValueError, TypeError) as exc:
        from opencomplai_cli import main as _main

        _main.err_console.print(
            f"[yellow]Warning:[/yellow] incident_contacts ignored: {escape(str(exc))}"
        )
        return []


@app.command("declare")
def declare_cmd(
    description: str = typer.Option(
        ..., "--description", help="What happened (stays local)"
    ),
    system_id: str | None = typer.Option(
        None, "--system-id", help="Default: from --manifest"
    ),
    aware_at: str | None = typer.Option(
        None, "--aware-at", help="ISO 8601; default declared-at"
    ),
    declared_at: str | None = typer.Option(
        None, "--declared-at", help="ISO 8601; default now"
    ),
    incident_class: IncidentClass = typer.Option(
        IncidentClass.unclassified, "--class", help="Incident class"
    ),
    file: Path = _FILE,
    manifest: Path = _MANIFEST,
    log: Path | None = _LOG,
    key: Path | None = _KEY,
    commit_ref: str = _COMMIT_REF,
) -> None:
    """Declare an incident, log it, move the system to incident mode, print its id."""
    from opencomplai_cli import main as _main

    with _guard():
        if system_id is None:
            data = _read_manifest(manifest)
            system_id = (data or {}).get("system_id")
            if not system_id:
                raise ValueError("no --system-id given and none found in the manifest")
        declared = inc.fmt_ts(inc.parse_ts(declared_at) if declared_at else _now())
        aware = inc.fmt_ts(inc.parse_ts(aware_at)) if aware_at else declared
        register = inc.load_register(file)
        rec = inc.declare(
            register,
            system_id=system_id,
            declared_at=declared,
            aware_at=aware,
            description=description,
            incident_class=incident_class,
        )
        payload = {
            "incident_id": rec.id,
            "system_id": rec.system_id,
            "incident_class": rec.incident_class.value,
            "declared_at": rec.declared_at,
            "aware_at": rec.aware_at,
        }
        out = _drive(ilog.EVENT_DECLARED, rec, payload, log, file, key, commit_ref)
        inc.save_register(file, register)
    _main.console.print(rec.id)
    _finish(out)


@app.command("classify")
def classify_cmd(
    id: str = typer.Option(..., "--id"),
    incident_class: IncidentClass = typer.Option(..., "--class"),
    file: Path = _FILE,
    log: Path | None = _LOG,
    key: Path | None = _KEY,
) -> None:
    """Set an incident's class (starts its deadline clock)."""
    with _guard():
        register = inc.load_register(file)
        rec = inc.classify(register, id, incident_class)
        payload = {
            "incident_id": rec.id,
            "system_id": rec.system_id,
            "incident_class": rec.incident_class.value,
        }
        _write_log(ilog.EVENT_CLASSIFIED, payload, log, file, key)
        inc.save_register(file, register)


@app.command("notify")
def notify_cmd(
    id: str = typer.Option(..., "--id"),
    party: str = typer.Option(..., "--party"),
    kind: PartyKind = typer.Option(..., "--kind"),
    sent_at: str | None = typer.Option(None, "--sent-at", help="ISO 8601; default now"),
    ref: str | None = typer.Option(None, "--ref"),
    file: Path = _FILE,
    log: Path | None = _LOG,
    key: Path | None = _KEY,
) -> None:
    """Record a notification sent to a party."""
    with _guard():
        register = inc.load_register(file)
        note = inc.Notification(
            party=party,
            kind=kind,
            sent_at=inc.fmt_ts(inc.parse_ts(sent_at) if sent_at else _now()),
            ref=ref,
        )
        rec = inc.add_notification(register, id, note)
        payload = {
            "incident_id": rec.id,
            "system_id": rec.system_id,
            "party_kind": note.kind.value,
            "party": note.party,
            "ref": note.ref,
            "sent_at": note.sent_at,
        }
        _write_log(ilog.EVENT_NOTIFIED, payload, log, file, key)
        inc.save_register(file, register)


@app.command("close")
def close_cmd(
    id: str = typer.Option(..., "--id"),
    note: str = typer.Option(..., "--note", help="Closure note (stays local)"),
    closed_at: str | None = typer.Option(
        None, "--closed-at", help="ISO 8601; default now"
    ),
    file: Path = _FILE,
    log: Path | None = _LOG,
    key: Path | None = _KEY,
    commit_ref: str = _COMMIT_REF,
) -> None:
    """Close an incident, log it and return the system to running."""
    with _guard():
        register = inc.load_register(file)
        when = inc.fmt_ts(inc.parse_ts(closed_at) if closed_at else _now())
        rec = inc.close(register, id, when, note)
        payload = {
            "incident_id": rec.id,
            "system_id": rec.system_id,
            "closed_at": rec.closed_at,
        }
        out = _drive(ilog.EVENT_CLOSED, rec, payload, log, file, key, commit_ref)
        inc.save_register(file, register)
    _finish(out)


@app.command("status")
def status_cmd(
    id: str | None = typer.Option(None, "--id"),
    system_id: str | None = typer.Option(None, "--system-id"),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output"),
    file: Path = _FILE,
    manifest: Path = _MANIFEST,
) -> None:
    """Show deadline clocks and pending contacts, computed at read time."""
    from opencomplai_cli import main as _main

    with _guard():
        register = inc.load_register(file)
        records = [inc.get_incident(register, id)] if id else list(register.incidents)
    if system_id:
        records = [r for r in records if r.system_id == system_id]
    contacts = _contacts(manifest)
    now = _now()
    rows = []
    for r in records:
        due = inc.deadline_at(r)
        rows.append(
            {
                "id": r.id,
                "system_id": r.system_id,
                "class": r.incident_class.value,
                "deadline_at": inc.fmt_ts(due) if due else None,
                "state": inc.deadline_state(r, now),
                "hours_remaining": inc.hours_remaining(r, now),
                "closed": r.closed_at is not None,
                "pending_contacts": [
                    c.party for c in inc.pending_contacts(r, contacts)
                ],
            }
        )
    if output == OutputFormat.json:
        sys.stdout.write(json.dumps({"incidents": rows}, indent=2) + "\n")
        return
    for row in rows:
        _main.console.print(
            f"{row['id']} {row['class']} state={row['state']} "
            f"deadline_at={row['deadline_at']} hours_remaining={row['hours_remaining']} "
            f"closed={row['closed']}",
            markup=False,
            highlight=False,
        )
        if row["state"] == "no_clock":
            _main.err_console.print(
                f"[yellow]Warning:[/yellow] {row['id']} is unclassified: no deadline clock yet"
            )
        for party in row["pending_contacts"]:
            _main.console.print(
                f"  pending contact: {party}", markup=False, highlight=False
            )
    if not rows:
        _main.console.print("No incidents.")


@app.command("export")
def export_cmd(
    id: str = typer.Option(..., "--id"),
    format: ExportFormat = typer.Option(ExportFormat.md, "--format"),
    output: Path | None = typer.Option(
        None, "--output", help="Write here instead of stdout"
    ),
    file: Path = _FILE,
    manifest: Path = _MANIFEST,
) -> None:
    """Export one incident, deterministic and free of today's date."""
    with _guard():
        rec = inc.get_incident(inc.load_register(file), id)
    contacts = _contacts(manifest)
    render = inc.render_json if format == ExportFormat.json else inc.render_markdown
    text = render(rec, contacts)
    if output is None:
        sys.stdout.write(text)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(text.encode("utf-8"))


@app.command("template")
def template_cmd(
    kind: TemplateKind = typer.Option(..., "--kind"),
    id: str = typer.Option(..., "--id"),
    party: str | None = typer.Option(None, "--party", help="Downstream party name"),
    party_kind: PartyKind | None = typer.Option(
        None, "--party-kind", help="deployer, importer or distributor"
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write here instead of stdout"
    ),
    file: Path = _FILE,
) -> None:
    """Render a DRAFT authority report or downstream notice (not legally reviewed)."""
    with _guard():
        rec = inc.get_incident(inc.load_register(file), id)
        incident = rec.model_dump(mode="json")
        if kind == TemplateKind.authority:
            text = itpl.render_authority_report(incident)
        else:
            if not party:
                raise ValueError("--party is required for the downstream template")
            if party_kind == PartyKind.authority:
                raise ValueError(
                    "--party-kind must be deployer, importer or distributor"
                )
            text = itpl.render_downstream_notice(
                incident, {"name": party, "kind": party_kind and party_kind.value}
            )
    if output is None:
        sys.stdout.write(text)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(text.encode("utf-8"))


def verify_incident_log(path: Path, pub_key: Path | None) -> VerifyResult:
    from opencomplai_cli import main as _main

    if not path.is_file():
        raise VerifyInputError(f"cannot read {path}: no such file")
    key = pub_key or _main._SIGNING_PUB
    if pub_key is not None and not key.is_file():
        raise VerifyInputError(f"public key file not found: {key}")
    anchor_kw = log_anchor()
    try:
        res = verify_log(
            path,
            SigningDomain.INCIDENT_LOG,
            public_pem=key.read_bytes() if key.is_file() else None,
            **anchor_kw,
        )
    except Exception:
        return VerifyResult("incident-log", "invalid", "malformed public key")
    tail = f"head={res.head} count={res.count}"
    if not res.ok:
        where = f" at entry {res.bad_seq}" if res.bad_seq else ""
        return VerifyResult(
            "incident-log", "invalid", f"{log_error(res.error)}{where}; {tail}"
        )
    if res.count == 0:
        return VerifyResult("incident-log", "invalid", f"{EMPTY_LOG}; {tail}")
    if res.signed_count < res.count:
        n = res.count - res.signed_count
        return VerifyResult(
            "incident-log", "unsigned", f"{n} of {res.count} entries unsigned; {tail}"
        )
    if res.verified_signatures:
        return VerifyResult("incident-log", "verified", f"signatures match; {tail}")
    return VerifyResult(
        "incident-log", "invalid", f"public key needed to verify signatures; {tail}"
    )


register_kind("incident-log", verify_incident_log, expect_keys=LOG_EXPECT_KEYS)
