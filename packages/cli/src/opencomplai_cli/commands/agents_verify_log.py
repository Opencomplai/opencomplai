"""
`opencomplai agents verify-log` and the `agent-log` kind of `opencomplai verify`.

Checks an agent decision log's hash chain and signatures, recomputes from the
manifest's declared agent inventory which entries were out of mandate (the log's
own flag is never trusted), and with `--vault` appends one `agent_action` event
per entry to the evidence vault, after storing the entry in the vault CAS and
checking the returned content hash. Only metadata goes into the ledger payload:
never `intent`, `input_hash` or `outcome`. A log that fails the chain check is
never sent anywhere.

A missing manifest is not an error: chain and signatures are checked and the
output says the mandate was not checked. `main` is imported lazily (main.py
imports this module's group).

Honest ceiling: a chain cannot show the newest entries were removed; the output
ends with `head=<sha256> count=<n>` so an operator can store an anchor for
`--expected-head` / `--expected-count`.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import typer
from opencomplai_core.agent_log_verify import (
    AgentLogReport,
    entry_bytes,
    entry_content_hash,
    vault_event_payload,
    verify_agent_log,
)
from opencomplai_core.models import SystemManifest
from opencomplai_core.signed_log import SignedLog
from opencomplai_core.signing import SigningDomain

from opencomplai_cli.commands.agents import app as agents_app
from opencomplai_cli.commands.halt import OutputFormat
from opencomplai_cli.commands.verify import (
    EMPTY_LOG,
    LOG_EXPECT_KEYS,
    VerifyInputError,
    VerifyResult,
    log_anchor,
    log_error,
    register_kind,
)

KIND = "agent-log"
_MANIFEST = Path("system-manifest.json")


class _ExitError(Exception):
    """Exit 2 for the command; for the `verify` kind, `invalid` names the detail."""

    def __init__(self, msg: str, invalid: str | None = None) -> None:
        super().__init__(msg)
        self.invalid = invalid


def _load(
    path: Path,
    manifest: Path,
    manifest_required: bool,
    pub_key: Path | None,
    **anchors,
) -> tuple[AgentLogReport, SystemManifest | None]:
    if not path.is_file():
        raise _ExitError(f"cannot read {path}: not a file")
    man = None
    if manifest.is_file():
        try:
            man = SystemManifest.model_validate_json(manifest.read_bytes())
        except (OSError, ValueError):
            raise _ExitError(
                f"{manifest} is not a valid system manifest", "manifest unreadable"
            ) from None
    elif manifest_required:
        raise _ExitError(f"cannot read {manifest}: not a file")
    if pub_key is None:
        from opencomplai_cli import main as _main

        pub_key = _main._SIGNING_PUB
        public_pem = pub_key.read_bytes() if pub_key.is_file() else None
    elif pub_key.is_file():
        public_pem = pub_key.read_bytes()
    else:
        raise _ExitError(f"public key file not found: {pub_key}")
    inv = man.agent_inventory if man else None
    try:
        report = verify_agent_log(path, public_pem=public_pem, inventory=inv, **anchors)
    except ValueError:
        raise _ExitError("malformed public key", "malformed public key") from None
    return report, man


def _anchor(report: AgentLogReport) -> str:
    return f"head={report.chain.head} count={report.chain.count}"


def _vault_append(
    report: AgentLogReport, path: Path, system_id: str, from_seq: int
) -> int:
    from opencomplai_cli import main as main_mod

    findings = {o.seq: o.reasons for o in report.out_of_mandate}
    sent = 0
    for entry in SignedLog(path, SigningDomain.AGENT_LOG).entries():
        if entry["seq"] < from_seq:
            continue
        want = entry_content_hash(entry)
        try:
            stored = main_mod._vault_request(
                "POST",
                "/v1/evidence/objects",
                {
                    "content_base64": base64.b64encode(entry_bytes(entry)).decode(),
                    "source": "agent-log",
                },
            )
            if stored.get("content_hash") != want:
                raise _ExitError(
                    f"vault returned a different content hash at seq {entry['seq']}"
                    f"; {sent} appended, resume with --vault-from-seq {entry['seq']}",
                )
            main_mod._vault_request(
                "POST",
                "/v1/evidence/events",
                {
                    "event_type": "agent_action",
                    "payload": vault_event_payload(
                        system_id, entry, want, findings.get(entry["seq"], ())
                    ),
                },
            )
        except _ExitError:
            raise
        except Exception as exc:
            raise _ExitError(
                f"vault request failed at seq {entry['seq']} ({exc.__class__.__name__})"
                f"; {sent} appended, resume with --vault-from-seq {entry['seq']}",
            ) from None
        sent += 1
    return sent


def verify_log_cmd(
    path: Path = typer.Argument(..., help="Agent decision log (JSON lines)"),
    manifest: Path = typer.Option(
        _MANIFEST, "--manifest", "-m", help="System manifest with an agent_inventory"
    ),
    pub_key: Path | None = typer.Option(
        None, "--pub-key", help="Public key PEM (default ~/.opencomplai/signing.pub)"
    ),
    require_signed: bool = typer.Option(False, "--require-signed"),
    expected_head: str | None = typer.Option(None, "--expected-head"),
    expected_count: int | None = typer.Option(None, "--expected-count"),
    vault: bool = typer.Option(
        False,
        "--vault",
        help="Append one agent_action event per entry to the evidence vault "
        "(needs OPENCOMPLAI_VAULT_URL). No cursor or dedupe: re-running appends "
        "duplicate events; use --vault-from-seq to resume.",
    ),
    vault_from_seq: int = typer.Option(1, "--vault-from-seq", min=1),
    system_id: str | None = typer.Option(None, "--system-id"),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Verify an agent decision log. Exit 0 ok, 1 tampered or out of mandate, 2 bad input."""
    # ponytail: no cursor or dedupe; add a stored cursor if operators run this on a schedule
    from opencomplai_cli import main as main_mod

    try:
        report, man = _load(
            path,
            manifest,
            manifest != _MANIFEST,
            pub_key,
            require_signed=require_signed,
            expected_head=expected_head,
            expected_count=expected_count,
        )
        chain = report.chain
        empty = chain.ok and chain.count == 0
        # Signatures a key could not check must not satisfy --require-signed.
        unverified = (
            require_signed
            and chain.ok
            and chain.signed_count > 0
            and not chain.verified_signatures
        )
        appended = None
        if vault and chain.ok and not unverified and not empty:
            if not main_mod._vault_configured():
                raise _ExitError("--vault needs OPENCOMPLAI_VAULT_URL to be set")
            sid = system_id or (man.system_id if man else None)
            if not sid:
                raise _ExitError("no system id: pass --system-id or a --manifest")
            appended = _vault_append(report, path, sid, vault_from_seq)
    except _ExitError as exc:
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(2)

    failed = not report.ok or unverified or empty
    if output == OutputFormat.json:
        typer.echo(
            json.dumps(
                {
                    "status": "invalid" if failed else "verified",
                    "chain": {
                        "ok": chain.ok,
                        "count": chain.count,
                        "head": chain.head,
                        "error": chain.error,
                        "bad_seq": chain.bad_seq,
                        "signed_count": chain.signed_count,
                        "verified_signatures": chain.verified_signatures,
                    },
                    "mandate_checked": report.mandate_checked,
                    "out_of_mandate": [
                        {
                            "seq": o.seq,
                            "agent_id": o.agent_id,
                            "tool": o.tool,
                            "reasons": list(o.reasons),
                        }
                        for o in report.out_of_mandate
                    ],
                    "vault": None if appended is None else {"appended": appended},
                }
            )
        )
    else:
        if not chain.ok:
            where = f" at seq {chain.bad_seq}" if chain.bad_seq is not None else ""
            typer.echo(f"INVALID: {chain.error}{where}")
        elif unverified:
            typer.echo("INVALID: signed entries need a public key to verify")
        elif empty:
            typer.echo("INVALID: empty log, no entries to verify")
        else:
            typer.echo(f"chain ok: {chain.count} entries, {chain.signed_count} signed")
        if chain.ok and not report.mandate_checked:
            typer.echo("mandate not checked: no manifest or no agent_inventory")
        for o in report.out_of_mandate:
            typer.echo(
                f"OUT OF MANDATE seq={o.seq} agent={o.agent_id} tool={o.tool} "
                f"reasons={','.join(o.reasons)}"
            )
        if appended is not None:
            typer.echo(f"vault: appended {appended} agent_action events")
        typer.echo(_anchor(report))
    sys.exit(1 if failed else 0)


def verify_agent_log_kind(path: Path, pub_key: Path | None) -> VerifyResult:
    try:
        report, _ = _load(path, _MANIFEST, False, pub_key, **log_anchor())
    except _ExitError as exc:
        if exc.invalid:
            return VerifyResult(KIND, "invalid", exc.invalid)
        raise VerifyInputError(str(exc)) from None
    c, anchor = report.chain, _anchor(report)
    if not c.ok:
        where = f" at seq {c.bad_seq}" if c.bad_seq is not None else ""
        return VerifyResult(KIND, "invalid", f"{log_error(c.error)}{where}; {anchor}")
    if c.count == 0:
        return VerifyResult(KIND, "invalid", f"{EMPTY_LOG}; {anchor}")
    if c.signed_count < c.count:
        n = c.count - c.signed_count
        return VerifyResult(
            KIND, "unsigned", f"{n} of {c.count} entries unsigned; {anchor}"
        )
    if c.signed_count and not c.verified_signatures:
        return VerifyResult(
            KIND, "invalid", f"public key needed to verify signatures; {anchor}"
        )
    if report.out_of_mandate:
        k = len(report.out_of_mandate)
        return VerifyResult(KIND, "invalid", f"out_of_mandate={k}; {anchor}")
    return VerifyResult(KIND, "verified", f"{c.count} entries; {anchor}")


register_kind(KIND, verify_agent_log_kind, expect_keys=LOG_EXPECT_KEYS)
agents_app.command("verify-log")(verify_log_cmd)
