"""
Committed, signed acceptance records (classification acceptance, trap approval).

A person who accepts a high-risk (Art. 6) classification, or approves a flagged
change, writes one signed JSON record into the repository
(``.opencomplai/acceptances/``) and commits it. ``check`` reads the record from
the repository, never from the home directory, so it works on ephemeral CI.

The record is bound to ``fingerprint_manifest`` (a watched manifest edit makes
it stale) and embeds its own public key, so verification needs no local key.
An embedded key proves the record was not altered after signing; it does not
prove who signed. Authority comes from git (who may merge the file) and from the
optional pin ``OPENCOMPLAI_TRUSTED_KEY_IDS`` (comma-separated ``key_id`` values).

Pure module: no clock, no network, no CLI. The caller supplies ``accepted_at``.
The statement is free text typed by the person; nothing here asserts legal
effect. source: product design, no external citation; confidence: medium;
needs_founder_review: true.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.models import ScanResult, ScanStatusArtifact, SystemManifest
from opencomplai_core.signing import (
    SigningDomain,
    sign_bundle_bytes,
    verify_bundle_bytes,
)

CLASSIFICATION_ACCEPTANCE = "classification_acceptance"
TRAP_APPROVAL = "trap_approval"
RECORD_TYPES = (CLASSIFICATION_ACCEPTANCE, TRAP_APPROVAL)
RECORD_DIR = ".opencomplai/acceptances"
ART6_CONTROL = "EU_AIA_ART6_HIGH_RISK"
SCHEMA_VERSION = 1
TRUSTED_KEY_IDS_ENV = "OPENCOMPLAI_TRUSTED_KEY_IDS"

_REQUIRED_STR = (
    "record_type",
    "system_id",
    "manifest_fingerprint",
    "accepted_by",
    "accepted_at",
    "statement",
    "public_key",
    "key_id",
)


@dataclass(frozen=True)
class AcceptanceStatus:
    """Outcome of ``evaluate_record``. ``reason`` never carries record content."""

    state: str  # valid|absent|malformed|unsigned|tampered|mismatch|untrusted|stale
    reason: str
    record: dict[str, Any] | None = None


def record_path(repo_root: Path, system_id: str, record_type: str) -> Path:
    """``repo_root/.opencomplai/acceptances/<slug>.<record_type>.json``."""
    slug = re.sub(r"[^A-Za-z0-9._-]", "_", system_id).lstrip(".") or "_"
    return repo_root / RECORD_DIR / f"{slug}.{record_type}.json"


def key_id_for(public_key_pem: str) -> str:
    return "sha256:" + hashlib.sha256(public_key_pem.encode("utf-8")).hexdigest()


def public_key_pem_from_private(private_pem: bytes) -> str:
    """SPKI PEM of the public half of an Ed25519 private key PEM."""
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(private_pem, password=None)
    return (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )


def build_record(
    *,
    record_type: str,
    system_id: str,
    manifest_fingerprint: str,
    accepted_by: str,
    statement: str,
    accepted_at: str,
    public_key_pem: str,
    change_context: str | None = None,
) -> dict[str, Any]:
    """Unsigned record. ``accepted_at`` is a caller-supplied ISO 8601 UTC string."""
    if record_type not in RECORD_TYPES:
        raise ValueError(f"unknown record_type: {record_type}")
    if record_type == TRAP_APPROVAL and not change_context:
        raise ValueError("a trap approval requires change_context")
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": record_type,
        "system_id": system_id,
        "manifest_fingerprint": manifest_fingerprint,
        "accepted_by": accepted_by,
        "accepted_at": accepted_at,
        "statement": statement,
        "public_key": public_key_pem,
        "key_id": key_id_for(public_key_pem),
    }
    if change_context is not None:
        record["change_context"] = change_context
    return record


def signing_bytes(record: Mapping[str, Any]) -> bytes:
    body = {k: v for k, v in record.items() if k != "signature"}
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def sign_record(record: dict[str, Any], key_path: Path) -> dict[str, Any]:
    signature = sign_bundle_bytes(
        signing_bytes(record), key_path, SigningDomain.CLASSIFICATION_ACCEPTANCE
    )
    return {**record, "signature": signature}


def trusted_key_ids_from_env(env: Mapping[str, str]) -> frozenset[str]:
    return frozenset(
        part.strip()
        for part in env.get(TRUSTED_KEY_IDS_ENV, "").split(",")
        if part.strip()
    )


def _signature_valid(record: Mapping[str, Any]) -> bool:
    # verify_bundle_bytes takes a key FILE, so the embedded key goes to a temp file.
    try:
        with tempfile.TemporaryDirectory() as tmp:
            pub = Path(tmp) / "record.pub"
            pub.write_text(record["public_key"], encoding="ascii")
            return verify_bundle_bytes(
                signing_bytes(record),
                record["signature"],
                pub,
                SigningDomain.CLASSIFICATION_ACCEPTANCE,
            )
    except Exception:
        return False


def evaluate_record(
    path: Path,
    manifest: SystemManifest,
    record_type: str,
    *,
    trusted_key_ids: frozenset[str] | None = None,
) -> AcceptanceStatus:
    """Classify the record at ``path`` for ``manifest``. Never raises."""
    try:
        return _evaluate(path, manifest, record_type, trusted_key_ids)
    except Exception:
        return AcceptanceStatus("malformed", "record could not be evaluated")


def _evaluate(
    path: Path,
    manifest: SystemManifest,
    record_type: str,
    trusted_key_ids: frozenset[str] | None,
) -> AcceptanceStatus:
    if not path.is_file():
        return AcceptanceStatus("absent", "no record")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AcceptanceStatus("malformed", "not valid JSON")
    if (
        not isinstance(record, dict)
        or record.get("schema_version") != SCHEMA_VERSION
        or not all(isinstance(record.get(k), str) for k in _REQUIRED_STR)
    ):
        return AcceptanceStatus("malformed", "missing or invalid fields")
    if (
        record["record_type"] != record_type
        or record["system_id"] != manifest.system_id
    ):
        return AcceptanceStatus("mismatch", "record is for another system or type")
    sig = record.get("signature")
    if not isinstance(sig, str) or not sig:
        return AcceptanceStatus("unsigned", "record has no signature")
    if record["key_id"] != key_id_for(record["public_key"]) or not _signature_valid(
        record
    ):
        return AcceptanceStatus("tampered", "signature does not verify")
    if trusted_key_ids and record["key_id"] not in trusted_key_ids:
        return AcceptanceStatus("untrusted", "signer key is not in the trusted key ids")
    if record["manifest_fingerprint"] != fingerprint_manifest(manifest):
        return AcceptanceStatus("stale", "manifest changed after the record was signed")
    if (
        not record["accepted_by"].strip()
        or not record["statement"].strip()
        or (record_type == TRAP_APPROVAL and not record.get("change_context"))
    ):
        return AcceptanceStatus("malformed", "required fields are empty")
    return AcceptanceStatus("valid", "record is valid", record)


def apply_acceptance(
    artifact: ScanStatusArtifact, status: AcceptanceStatus
) -> ScanStatusArtifact:
    """Stop Art. 6 counting as a failure when a valid acceptance covers it.

    Removes only ``ART6_CONTROL`` from a CONTROL_FAIL artifact. Art. 5
    (POLICY_BLOCK), traps, validation failures and every other failed control
    are untouched.
    """
    if (
        status.state != "valid"
        or status.record is None
        or status.record.get("record_type") != CLASSIFICATION_ACCEPTANCE
        or ART6_CONTROL not in artifact.failed_controls
        or artifact.result != ScanResult.CONTROL_FAIL
    ):
        return artifact
    remaining = [c for c in artifact.failed_controls if c != ART6_CONTROL]
    return artifact.model_copy(
        update={
            "failed_controls": remaining,
            "result": ScanResult.CONTROL_FAIL if remaining else ScanResult.PASS,
        }
    )
