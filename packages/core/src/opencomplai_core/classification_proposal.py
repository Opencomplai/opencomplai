"""A classification proposal as a file a person can review and confirm.

``scan --propose`` suggests a classification from call-site signals and writes
this document (``classification-proposal.json``). It stays ``unconfirmed`` until
a person runs ``opencomplai accept --proposal``, which signs a
``classification_proposal_confirmation`` record (see ``acceptance``). The record
states only that a person confirmed the proposal as shown; it never asserts a
legal classification and no verdict reads it in this module.

The proposal carries its own digest, so an edit after it was written (or after it
was confirmed) is detectable. Pure module: no clock, no network, no CLI.
source: product design, no external citation; confidence: medium;
needs_founder_review: true.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from opencomplai_core.acceptance import (
    PROPOSAL_CONFIRMATION,
    AcceptanceStatus,
    evaluate_record,
)
from opencomplai_core.models import SystemManifest

PROPOSAL_FILENAME = "classification-proposal.json"
PROPOSAL_DOCUMENT_TYPE = "classification_proposal"
PROPOSAL_SCHEMA_VERSION = 1
NOTICE = (
    "Suggested from code signals; unconfirmed until a person runs "
    "`opencomplai accept --proposal`. Not a legal determination: the declared "
    "purpose stays authoritative."
)

_REQUIRED_STR = (
    "document_type",
    "status",
    "notice",
    "system_id",
    "commit_ref",
    "scanner_version",
    "scan_input_digest",
    "scan_report_hash",
    "manifest_fingerprint",
    "declared_purpose",
    "area",
    "confidence",
    "proposal_sha256",
)
_REQUIRED_LIST = ("evidence", "minority_evidence", "prohibited_signals")


def proposal_digest(doc: Mapping[str, Any]) -> str:
    """``sha256:`` over the canonical JSON of ``doc`` without ``proposal_sha256``."""
    body = {k: v for k, v in doc.items() if k != "proposal_sha256"}
    raw = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def build_proposal_document(
    *,
    system_id: str,
    commit_ref: str,
    scanner_version: str,
    scan_input_digest: str,
    scan_report_hash: str,
    manifest_fingerprint: str,
    declared_purpose: str,
    area: str,
    confidence: str,
    evidence: Sequence[Any],
    minority_evidence: Sequence[Any],
    prohibited_signals: Sequence[Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """The unconfirmed proposal document, ``proposal_sha256`` last."""
    doc: dict[str, Any] = {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "document_type": PROPOSAL_DOCUMENT_TYPE,
        "status": "unconfirmed",
        "notice": NOTICE,
        "system_id": system_id,
        "commit_ref": commit_ref,
        "scanner_version": scanner_version,
        "scan_input_digest": scan_input_digest,
        "scan_report_hash": scan_report_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "declared_purpose": declared_purpose,
        "area": area,
        "confidence": confidence,
        "evidence": list(evidence),
        "minority_evidence": list(minority_evidence),
        "prohibited_signals": list(prohibited_signals),
        "proposal": dict(proposal),
    }
    doc["proposal_sha256"] = proposal_digest(doc)
    return doc


def load_proposal(path: Path) -> dict[str, Any]:
    """Read and verify a proposal file. ``ValueError`` names the problem only."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError("proposal file could not be read") from exc
    except ValueError as exc:
        raise ValueError("proposal file is not valid JSON") from exc
    if not isinstance(doc, dict):
        raise ValueError("proposal file is not a JSON object")
    if doc.get("document_type") != PROPOSAL_DOCUMENT_TYPE:
        raise ValueError("proposal file has the wrong document_type")
    if doc.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
        raise ValueError("proposal file has an unsupported schema_version")
    missing = [k for k in _REQUIRED_STR if not isinstance(doc.get(k), str)]
    missing += [k for k in _REQUIRED_LIST if not isinstance(doc.get(k), list)]
    if not isinstance(doc.get("proposal"), dict):
        missing.append("proposal")
    if missing:
        raise ValueError("proposal file is missing fields: " + ", ".join(missing))
    if doc["proposal_sha256"] != proposal_digest(doc):
        raise ValueError("proposal file was edited after it was written")
    return doc


def confirmation_status(
    proposal_path: Path,
    record_path: Path,
    manifest: SystemManifest,
    *,
    trusted_key_ids: frozenset[str] | None = None,
) -> AcceptanceStatus:
    """State of the confirmation record for the proposal file on disk.

    ``valid`` only when the record verifies for this manifest AND the proposal
    file still has the digest the person confirmed; otherwise the record's own
    state, or ``proposal_changed`` when the file was edited, replaced or removed.
    """
    status = evaluate_record(
        record_path, manifest, PROPOSAL_CONFIRMATION, trusted_key_ids=trusted_key_ids
    )
    if status.state != "valid" or status.record is None:
        return status
    try:
        doc = load_proposal(proposal_path)
    except ValueError:
        return AcceptanceStatus(
            "proposal_changed", "proposal file is missing or was edited"
        )
    if doc["proposal_sha256"] != status.record.get("proposal_sha256"):
        return AcceptanceStatus(
            "proposal_changed", "proposal differs from the one that was confirmed"
        )
    return status
