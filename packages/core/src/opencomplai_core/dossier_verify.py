"""
Annex IV dossier verification.

`verify_dossier` checks a dossier dict against an Ed25519 public key and
returns a `DossierVerdict` with a distinct code per failure. Only Ed25519
signatures verify: an unsigned dossier and a legacy symmetric one each get
their own code, and nothing here raises on hostile input.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opencomplai_core.dossier import AnnexIVDossier
from opencomplai_core.dossier_generator import BUNDLE_EXCLUDE
from opencomplai_core.signing import SigningDomain, verify_bundle_bytes

__all__ = ["DossierVerdict", "verify_dossier"]


@dataclass(frozen=True)
class DossierVerdict:
    ok: bool
    code: str  # OK | MALFORMED | UNSIGNED | UNSUPPORTED_SIGNATURE | CHECKSUM_MISMATCH | BAD_SIGNATURE
    detail: str


def _no(code: str, detail: str) -> DossierVerdict:
    return DossierVerdict(False, code, detail)


def verify_dossier(dossier: dict[str, Any], pub_key_path: Path) -> DossierVerdict:
    try:
        parsed = AnnexIVDossier.model_validate(dossier)
    except Exception:
        return _no("MALFORMED", "not a valid Annex IV dossier")

    if not parsed.signature or parsed.signature_status == "unsigned":
        return _no("UNSIGNED", "no signature present")
    if parsed.signature_status != "ed25519":
        return _no(
            "UNSUPPORTED_SIGNATURE",
            f"signature status {parsed.signature_status!r} cannot be verified; "
            "only ed25519 is supported",
        )

    try:
        bundle = parsed.model_dump_json(exclude=BUNDLE_EXCLUDE).encode("utf-8")
        if parsed.bundle_checksum != f"sha256:{hashlib.sha256(bundle).hexdigest()}":
            return _no("CHECKSUM_MISMATCH", "content does not match bundle_checksum")
        ok = verify_bundle_bytes(
            bundle, parsed.signature, pub_key_path, SigningDomain.DOSSIER_BUNDLE
        )
    except Exception:
        return _no("BAD_SIGNATURE", "malformed signature or public key")
    if not ok:
        return _no("BAD_SIGNATURE", "signature does not match")
    return DossierVerdict(True, "OK", "signature matches")
