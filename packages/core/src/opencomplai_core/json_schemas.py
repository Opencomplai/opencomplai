"""JSON Schema documents for the compliance artifact, the gap report, the
Annex IV dossier, the evidence package and the attestation bundle.

Generated from the pydantic models (scripts/generate_artifact_schemas.py writes
them to data/, the evidence package and attestation bundle schemas included).
`schema_version` lives in the schema document only, never on the artifact
models: a model field would change signed artifact bytes. (The attestation
bundle is the one exception: it tags itself `attestation_bundle/v1`.)
"""

from __future__ import annotations

from typing import Any

from opencomplai_core.attestation_bundle import SCHEMA_ID, AttestationBundle
from opencomplai_core.dossier import AnnexIVDossier
from opencomplai_core.evidence_package import EvidencePackage
from opencomplai_core.models import GapReport, ScanStatusArtifact

SCHEMA_VERSION = "1"
_DRAFT = "https://json-schema.org/draft/2020-12/schema"
ARTIFACT_SCHEMA_ID = "https://schemas.opencomplai.dev/scan_status_artifact/v1"
GAP_REPORT_SCHEMA_ID = "https://schemas.opencomplai.dev/gap_report/v1"
DOSSIER_SCHEMA_ID = "https://schemas.opencomplai.dev/annex_iv_dossier/v1"
EVIDENCE_PACKAGE_SCHEMA_ID = "https://schemas.opencomplai.dev/evidence_package/v1"
ATTESTATION_BUNDLE_SCHEMA_ID = SCHEMA_ID


def _build(model: Any, schema_id: str) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema["$schema"] = _DRAFT
    schema["$id"] = schema_id
    schema["schema_version"] = SCHEMA_VERSION
    return schema


def build_artifact_schema() -> dict[str, Any]:
    return _build(ScanStatusArtifact, ARTIFACT_SCHEMA_ID)


def build_gap_report_schema() -> dict[str, Any]:
    return _build(GapReport, GAP_REPORT_SCHEMA_ID)


def build_dossier_schema() -> dict[str, Any]:
    return _build(AnnexIVDossier, DOSSIER_SCHEMA_ID)


def build_evidence_package_schema() -> dict[str, Any]:
    return _build(EvidencePackage, EVIDENCE_PACKAGE_SCHEMA_ID)


def build_attestation_bundle_schema() -> dict[str, Any]:
    return _build(AttestationBundle, ATTESTATION_BUNDLE_SCHEMA_ID)
