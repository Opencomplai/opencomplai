"""Derive the signer key id shown in check reports (never stored in the artifact)."""

from __future__ import annotations

from pathlib import Path


def signer_key_id(key_path: Path) -> str:
    """`sha256:<16 hex>` of the public key behind the signing key, or "" on any failure."""
    try:
        from opencomplai_core.agent_attestation import (
            key_id_for_public_pem,
            public_pem_for_private_pem,
        )
        from opencomplai_core.signing import resolve_key

        return key_id_for_public_pem(public_pem_for_private_pem(resolve_key(key_path)))
    except Exception:  # cryptography is optional; reports are best effort
        return ""
