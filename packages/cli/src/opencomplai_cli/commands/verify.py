"""
CLI `verify` command (decision E-7: one verify command, dispatched by kind).

`opencomplai verify <path> [--kind K]` checks a signed file and reports one of
three statuses: `verified`, `unsigned` (no signature present) or `invalid`
(signature does not match, or the signature / key is malformed). Only the
`artifact` kind is registered here. Later epics add their own kind with one
`register_kind(name, handler, expect_keys=...)` call; they do not edit the dispatch
below. `--expect KEY=VALUE` is accepted only for keys the kind declares: `now` and
`mandate_sha256` for agent-attestation, `head` and `count` for the three log kinds,
none for every other kind (anything else exits 2).

A handler takes ``(path, pub_key)`` and returns a `VerifyResult`. It raises
`VerifyInputError` for input problems (exit 2): file missing, bad JSON or
schema, missing key file. The command never writes or modifies any file.

Registered as a top-level command by `main.py`, which is obtained lazily here
to avoid a circular import (same approach as `commands/halt.py`).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

import typer
from opencomplai_core import signing
from opencomplai_core.models import ScanStatusArtifact

from opencomplai_cli.commands.halt import OutputFormat


class VerifyInputError(Exception):
    """The input cannot be verified at all (exit 2), as opposed to failing."""


@dataclass(frozen=True)
class VerifyResult:
    kind: str
    status: str  # "verified" | "unsigned" | "invalid"
    detail: str


Handler = Callable[[Path, Path | None], VerifyResult]
_KINDS: dict[str, Handler] = {}
_EXPECT_KEYS: dict[str, frozenset[str]] = {}
LOG_EXPECT_KEYS = ("head", "count")
EMPTY_LOG = "empty log: no entries to verify"
# ponytail: module-level carrier instead of changing the handler signature for every
# kind; revisit if a third kind needs it. Cleared and refilled by every verify_cmd call.
EXPECT: dict[str, str] = {}


def register_kind(name: str, handler: Handler, expect_keys: Iterable[str] = ()) -> None:
    _KINDS[name] = handler
    _EXPECT_KEYS[name] = frozenset(expect_keys)


def log_anchor() -> dict:
    """`verify_log` anchor kwargs from `--expect head=` / `count=` (read at call time)."""
    out: dict = {}
    if "head" in EXPECT:
        out["expected_head"] = EXPECT["head"]
    if "count" in EXPECT:
        value = EXPECT["count"]
        if not (value.isascii() and value.isdigit()):
            raise VerifyInputError(
                f"--expect count needs a whole number, got '{value}'"
            )
        out["expected_count"] = int(value)
    return out


def log_error(code: str | None) -> str:
    """Operator wording for a `verify_log` error code."""
    return {
        "head": "head does not match --expect head",
        "count": "count does not match --expect count",
    }.get(code or "", code or "invalid")


def _main_module():
    from opencomplai_cli import main as _main

    return _main


def _verify_artifact_kind(path: Path, pub_key: Path | None) -> VerifyResult:
    try:
        artifact = ScanStatusArtifact.model_validate_json(path.read_bytes())
    except OSError as exc:
        raise VerifyInputError(f"cannot read {path}: {exc.strerror or exc}") from None
    except ValueError:
        raise VerifyInputError(
            f"{path} is not a valid scan status artifact (JSON/schema error)"
        ) from None

    # Must come first: verify_artifact returns False for unsigned AND tampered.
    if artifact.signature is None:
        return VerifyResult("artifact", "unsigned", "no signature present")

    key = pub_key or _main_module()._SIGNING_PUB
    if not key.is_file():
        raise VerifyInputError(f"public key file not found: {key}")
    try:
        ok = signing.verify_artifact(artifact, key)
    except Exception:
        return VerifyResult("artifact", "invalid", "malformed signature or public key")
    if ok:
        return VerifyResult("artifact", "verified", "signature matches")
    return VerifyResult("artifact", "invalid", "signature does not match")


register_kind("artifact", _verify_artifact_kind)

_HUMAN = {
    "verified": "verified: {detail}",
    "unsigned": "unsigned: {detail}",
    "invalid": "INVALID: {detail}",
}


def verify_cmd(
    path: Path = typer.Argument(..., help="File to verify"),
    kind: str = typer.Option("artifact", "--kind", help="What kind of file this is"),
    pub_key: Path | None = typer.Option(
        None,
        "--pub-key",
        help="Public key PEM (defaults to ~/.opencomplai/signing.pub)",
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
    expect: list[str] | None = typer.Option(
        None,
        "--expect",
        help="Extra offline checks, KEY=VALUE, repeatable, each key once. "
        "agent-attestation: now=<ISO UTC>, mandate_sha256=sha256:... ; "
        "oversight-log, incident-log, agent-log: head=<hash>, count=<n>. "
        "Other kinds take none; an unsupported key exits 2.",
    ),
) -> None:
    """Verify a signed file. Exit 0 verified, 1 unsigned or invalid, 2 bad input."""
    handler = _KINDS.get(kind)
    EXPECT.clear()
    try:
        for pair in expect or []:
            key, sep, value = pair.partition("=")
            if not sep or not key:
                raise VerifyInputError(f"--expect needs KEY=VALUE, got '{pair}'")
            if key in EXPECT:
                raise VerifyInputError(f"--expect {key} given more than once")
            EXPECT[key] = value
        if handler is None:
            raise VerifyInputError(
                f"unknown kind '{kind}'; registered kinds: {', '.join(sorted(_KINDS))}"
            )
        extra = set(EXPECT) - _EXPECT_KEYS.get(kind, frozenset())
        if extra:
            ok = ", ".join(sorted(_EXPECT_KEYS.get(kind, ()))) or "none"
            raise VerifyInputError(
                f"kind '{kind}' does not support --expect {', '.join(sorted(extra))}; "
                f"supported: {ok}"
            )
        result = handler(path, pub_key)
    except VerifyInputError as exc:
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(2)

    if output == OutputFormat.json:
        typer.echo(json.dumps(asdict(result)))
    else:
        typer.echo(_HUMAN[result.status].format(detail=result.detail))
    sys.exit(0 if result.status == "verified" else 1)
