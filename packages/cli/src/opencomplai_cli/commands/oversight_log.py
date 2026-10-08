"""
Signed, hash-chained oversight log for `approve` and `resume`.

`halt.py` appends one entry per approval and one per resume to
`oversight-log.json` in the state directory (one JSON object per line, the
`signed_log.SignedLog` format, domain `SigningDomain.OVERSIGHT_LOG`). Each entry
names the approver's role, checked against the manifest's structured
`human_oversight` block when the manifest declares one. This module also
registers the `oversight-log` kind with `opencomplai verify`.

`main.py` imports this module (next to `verify_dossier`) so the kind is
registered in every process; `halt.py` imports it lazily inside the commands.
`main` is imported lazily here too, never at module load.

Honest ceiling: a chain cannot show that the newest entries were removed.
Truncation is only detectable against a head/count anchor stored elsewhere;
`verify` prints `head=<sha256> count=<n>` so an operator can keep one. Refused
resumes are not logged.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from opencomplai_core.models import SystemManifest
from opencomplai_core.signed_log import SignedLog, verify_log
from opencomplai_core.signing import SigningDomain, SigningKeyError, resolve_key

from opencomplai_cli.commands.verify import (
    EMPTY_LOG,
    LOG_EXPECT_KEYS,
    VerifyInputError,
    VerifyResult,
    log_anchor,
    log_error,
    register_kind,
)

LOG_NAME = "oversight-log.json"


def _now() -> str:
    """The only clock read for the log; tests patch it (E-14)."""
    return datetime.now(UTC).isoformat()


def log_path() -> Path:
    from opencomplai_cli import main as _main

    return _main._state_dir() / LOG_NAME


def declared_roles(manifest_path: Path) -> list[str]:
    """Roles of the manifest's structured oversight block; `[]` if no file or no block."""
    if not manifest_path.exists():
        return []
    try:
        manifest = SystemManifest.model_validate_json(manifest_path.read_text())
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read manifest {manifest_path}: {exc}") from None
    if manifest.human_oversight is None:
        return []
    return list(dict.fromkeys(r.role for r in manifest.human_oversight.roles))


def resolve_role(manifest_path: Path, role: str | None) -> tuple[str | None, bool]:
    """`(role, role_declared)`; raises ValueError if the manifest declares roles and `role` is not one."""
    declared = declared_roles(manifest_path)
    if not declared:
        return role, False
    allowed = ", ".join(declared)
    if role is None:
        raise ValueError(f"--role is required; the manifest declares: {allowed}")
    if role not in declared:
        raise ValueError(
            f"role '{role}' is not declared in the manifest; allowed: {allowed}"
        )
    return role, True


def append_entry(payload: dict, key_path: Path | None) -> dict:
    """Append `payload`, signed when a key resolves, unsigned otherwise. OSError propagates."""
    try:
        private_pem = resolve_key(key_path)
    except SigningKeyError:
        private_pem = None
    return SignedLog(log_path(), SigningDomain.OVERSIGHT_LOG).append(
        payload, ts=_now(), private_pem=private_pem
    )


def verify_oversight_log(path: Path, pub_key: Path | None) -> VerifyResult:
    if not path.is_file():
        raise VerifyInputError(f"cannot read {path}: not a file")
    if pub_key is None:
        from opencomplai_cli import main as _main

        pub_key = _main._SIGNING_PUB
    public_pem = pub_key.read_bytes() if pub_key.is_file() else None
    anchor_kw = log_anchor()
    try:
        v = verify_log(
            path, SigningDomain.OVERSIGHT_LOG, public_pem=public_pem, **anchor_kw
        )
    except ValueError:
        return VerifyResult("oversight-log", "invalid", "malformed public key")
    anchor = f"head={v.head} count={v.count}"
    if not v.ok:
        where = f" at seq {v.bad_seq}" if v.bad_seq is not None else ""
        return VerifyResult(
            "oversight-log", "invalid", f"{log_error(v.error)}{where}; {anchor}"
        )
    if v.count == 0:
        return VerifyResult("oversight-log", "invalid", f"{EMPTY_LOG}; {anchor}")
    if v.signed_count < v.count:
        n = v.count - v.signed_count
        return VerifyResult(
            "oversight-log", "unsigned", f"{n} of {v.count} entries unsigned; {anchor}"
        )
    if not v.verified_signatures:
        return VerifyResult(
            "oversight-log",
            "invalid",
            f"public key needed to verify signatures; {anchor}",
        )
    return VerifyResult(
        "oversight-log", "verified", f"{v.count} entries signed; {anchor}"
    )


register_kind("oversight-log", verify_oversight_log, expect_keys=LOG_EXPECT_KEYS)
