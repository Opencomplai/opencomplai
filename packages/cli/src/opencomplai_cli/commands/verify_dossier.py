"""
`opencomplai verify --kind dossier` (decision E-7).

Registers the `dossier` kind with the `verify` dispatcher on import. Verified
means a valid Ed25519 signature over the dossier bundle; unsigned is reported
distinctly; a legacy HMAC-only, tampered or wrong-key dossier is invalid.
The public key is read lazily from `main` (same approach as `commands/halt.py`
and `commands/verify.py`) to avoid a circular import.
"""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_core.dossier_verify import verify_dossier

from opencomplai_cli.commands.verify import (
    VerifyInputError,
    VerifyResult,
    register_kind,
)


def _main_module():
    from opencomplai_cli import main as _main

    return _main


def verify_dossier_kind(path: Path, pub_key: Path | None) -> VerifyResult:
    try:
        dossier = json.loads(path.read_bytes())
    except OSError as exc:
        raise VerifyInputError(f"cannot read {path}: {exc.strerror or exc}") from None
    except ValueError:
        raise VerifyInputError(f"{path} is not valid JSON") from None

    key = pub_key or _main_module()._SIGNING_PUB
    verdict = verify_dossier(dossier, key)
    # An unsigned dossier needs no key; anything else does.
    if verdict.code != "UNSIGNED" and not key.is_file():
        raise VerifyInputError(f"public key file not found: {key}")
    if verdict.ok:
        return VerifyResult("dossier", "verified", verdict.detail)
    if verdict.code == "UNSIGNED":
        return VerifyResult("dossier", "unsigned", verdict.detail)
    return VerifyResult("dossier", "invalid", f"{verdict.code}: {verdict.detail}")


register_kind("dossier", verify_dossier_kind)
