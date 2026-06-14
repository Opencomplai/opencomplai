"""Canonical hashing for scanner evidence and reports (no source content)."""

from __future__ import annotations

import hashlib
import json

from opencomplai_core.models import CorroborationReport, EvidenceItem


def _canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def token_hash(label: str) -> str:
    digest = hashlib.sha256(label.lower().encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def evidence_id(
    detector_id: str, token_label: str, location: str, evidence_kind: str
) -> str:
    raw = f"{detector_id}|{token_label}|{location}|{evidence_kind}"
    return f"ev_sha256:{hashlib.sha256(raw.encode()).hexdigest()}"


def evidence_item_hash(item: EvidenceItem) -> str:
    canonical = {
        "evidence_id": item.evidence_id,
        "evidence_kind": item.evidence_kind.value,
        "category": item.category.value,
        "token_hash": item.token_hash,
        "token_label": item.token_label,
        "locations": sorted(item.locations),
        "scope": item.scope.value,
        "reachability": item.reachability.value,
        "detector_id": item.detector_id,
        "rationale_code": item.rationale_code,
        "confidence": round(item.confidence, 6),
    }
    digest = hashlib.sha256(_canonical_json(canonical).encode()).hexdigest()
    return f"sha256:{digest}"


def report_hash(report: CorroborationReport) -> str:
    canonical = {
        "scan_id": report.scan_id,
        "system_id": report.system_id,
        "commit_ref": report.commit_ref,
        "scanner_version": report.scanner_version,
        "input_digest": report.input_digest,
        "config_hash": report.config_hash,
        "declared_purpose": report.declared_purpose,
        "declared_categories": sorted(report.declared_categories),
        "detected_categories": sorted(report.detected_categories),
        "discrepancies": sorted(report.discrepancies),
        "severity": report.severity.value,
        "evidence_locations": sorted(
            loc for ev in report.evidence for loc in ev.locations
        ),
        "finding_ids": sorted(f.finding_id for f in report.findings),
    }
    digest = hashlib.sha256(_canonical_json(canonical).encode()).hexdigest()
    return f"sha256:{digest}"
