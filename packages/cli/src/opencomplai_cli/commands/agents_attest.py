"""
`opencomplai agents attest` and the `agent-attestation` kind of `opencomplai verify`.

An attestation is a signed statement that the holder of a key vouched for one
agent's mandate hash until an expiry (`agent_attestation/v1`, see
`opencomplai_core.agent_attestation`). It is produced and checked offline and is
never uploaded. `verified` means a key holder signed that hash; it says nothing
about whether the mandate is lawful or complete.

`main` is imported lazily (main.py imports the `agents` group this attaches to).
`attest` always signs: a missing key exits 2 before anything is written.
`key_id` is the normalised fingerprint of the public PEM text (see core); it is
NOT the value `opencomplai keys rotate` prints, which hashes the raw file bytes.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer
from opencomplai_core.agent_attestation import (
    mandate_sha256,
    sign_attestation,
    verify_attestation,
)
from opencomplai_core.agent_inventory import check_inventory
from opencomplai_core.models import SystemManifest
from opencomplai_core.signing import SigningKeyError, resolve_key

from opencomplai_cli.commands.agents import app as agents_app
from opencomplai_cli.commands.halt import OutputFormat
from opencomplai_cli.commands.verify import (
    EXPECT,
    VerifyInputError,
    VerifyResult,
    register_kind,
)

_TS = "%Y-%m-%dT%H:%M:%SZ"
KIND = "agent-attestation"


def _now() -> datetime:
    """The one clock seam; tests patch it."""
    return datetime.now(UTC)


def _main_module():
    from opencomplai_cli import main as _main

    return _main


def _fail(msg: str) -> None:
    _main_module().err_console.print(
        f"[red]Error:[/red] {msg}", markup=True, highlight=False
    )
    sys.exit(2)


def attest_cmd(
    manifest: Path = typer.Option(
        Path("system-manifest.json"), "--manifest", "-m", help="System manifest JSON"
    ),
    agent_id: str = typer.Option(..., "--agent-id", help="Id of the agent to attest"),
    issuer: str = typer.Option(
        ..., "--issuer", help="Who is vouching (printable ASCII, up to 128 characters)"
    ),
    valid_days: int = typer.Option(30, "--valid-days", min=1, max=365),
    out: Path | None = typer.Option(
        None, "--out", help="Output file (default agent-attestation-<agent_id>.json)"
    ),
    key: Path | None = typer.Option(
        None, "--key", help="Private key PEM (default ~/.opencomplai/signing.key)"
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Sign a statement that this key holder vouches for an agent's mandate hash."""
    try:
        man = SystemManifest.model_validate_json(manifest.read_bytes())
    except OSError as exc:
        _fail(f"cannot read {manifest}: {exc.strerror or exc}")
    except ValueError:
        _fail(f"{manifest} is not a valid system manifest")
    inv = man.agent_inventory
    if inv is None:
        _fail("manifest has no agent_inventory")
    errors = check_inventory(inv)
    if errors:
        _fail("agent inventory is invalid: " + "; ".join(errors))
    agent = next((a for a in inv.agents if a.id == agent_id), None)
    if agent is None:
        _fail(
            f"unknown agent '{agent_id}'; known ids: {', '.join(a.id for a in inv.agents)}"
        )
    if agent.mandate is None:
        _fail(f"agent '{agent_id}' has no mandate to attest")
    target = out or Path(f"agent-attestation-{agent_id}.json")
    if target.exists():
        _fail(f"{target} already exists; choose another --out")
    try:
        private_pem = resolve_key(key or _main_module()._SIGNING_KEY)
    except SigningKeyError as exc:
        _fail(str(exc))

    issued = _now().astimezone(UTC).replace(microsecond=0)
    try:
        att = sign_attestation(
            agent_id=agent_id,
            system_id=man.system_id,
            mandate_sha256=mandate_sha256(agent.mandate),
            issuer=issuer,
            issued_at=issued.strftime(_TS),
            expires_at=(issued + timedelta(days=valid_days)).strftime(_TS),
            private_pem=private_pem,
        )
    except ValueError as exc:
        _fail(
            f"cannot build attestation ({exc.__class__.__name__}); check --issuer and the key"
        )
    try:
        with open(target, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(att, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        _fail(f"cannot write {target}: {exc.strerror or exc}")

    if output == OutputFormat.json:
        typer.echo(json.dumps(att))
    else:
        typer.echo(f"agent_id:       {att['agent_id']}")
        typer.echo(f"mandate_sha256: {att['mandate_sha256']}")
        typer.echo(f"expires_at:     {att['expires_at']}")
        typer.echo(f"key_id:         {att['key_id']}")
        typer.echo(f"written:        {target}")


def _parse_now(value: str | None) -> datetime:
    if value is None:
        return _now()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise VerifyInputError(
            f"--expect now= is not an ISO 8601 UTC time: {value}"
        ) from None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def verify_attestation_file(path: Path, pub_key: Path | None) -> VerifyResult:
    try:
        data = json.loads(path.read_bytes())
    except OSError as exc:
        raise VerifyInputError(f"cannot read {path}: {exc.strerror or exc}") from None
    except ValueError:
        raise VerifyInputError(f"{path} is not valid JSON") from None
    if not isinstance(data, dict):
        raise VerifyInputError(f"{path} is not a JSON object")
    key = pub_key or _main_module()._SIGNING_PUB
    if not key.is_file():
        raise VerifyInputError(f"public key file not found: {key}")
    res = verify_attestation(
        data,
        key.read_bytes(),
        now=_parse_now(EXPECT.get("now")),
        expect_mandate_sha256=EXPECT.get("mandate_sha256"),
    )
    if res.status == "verified":
        return VerifyResult(
            KIND,
            "verified",
            f"signature matches; agent_id={data['agent_id']} expires_at={data['expires_at']}",
        )
    if res.status == "unsigned":
        return VerifyResult(KIND, "unsigned", "no signature present")
    return VerifyResult(KIND, "invalid", res.code or "invalid")


register_kind(KIND, verify_attestation_file, expect_keys=("now", "mandate_sha256"))
agents_app.command("attest")(attest_cmd)
