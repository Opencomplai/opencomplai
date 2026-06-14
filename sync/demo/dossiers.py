"""
Dossier envelope fixture generator for HIGH-risk demo systems.

Produces the payload consumed by POST /v1/docs/generate (doc-generator)
and the follow-up POST /v1/pro/ingest/dossier-metadata (evidence-vault).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime


def _sha256(data: str) -> str:
    return "sha256:" + hashlib.sha256(data.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Dossier manifest payloads (sent to doc-generator)
# ---------------------------------------------------------------------------

DOSSIER_MANIFESTS: dict[str, list[dict]] = {
    "demo-credit-scoring-v1": [
        {
            "system_id": "demo-credit-scoring-v1",
            "commit_ref": "v1.3.0-demo",
            "intended_purpose": (
                "Automated scoring of consumer creditworthiness to support "
                "lending decisions by financial institutions."
            ),
            "provider_name": "Demo Tenant — Finance Division",
            "training_data_description": (
                "Historical loan performance data from 2018-2023, "
                "anonymised per GDPR Art. 25."
            ),
        }
    ],
    "demo-hr-hiring-v2": [
        {
            "system_id": "demo-hr-hiring-v2",
            "commit_ref": "v2.0.1-demo",
            "intended_purpose": (
                "Ranks job applicants using structured interview scoring, "
                "CV parsing, and behavioural signal analysis."
            ),
            "provider_name": "Demo Tenant — HR Division",
            "training_data_description": (
                "Anonymised recruitment outcomes from 15 000 past hires, "
                "balanced across gender and ethnicity strata."
            ),
        },
        {
            "system_id": "demo-hr-hiring-v2",
            "commit_ref": "v2.0.1-remediated-demo",
            "intended_purpose": "Post-remediation re-validation dossier after HITL halt.",
            "provider_name": "Demo Tenant — HR Division",
            "training_data_description": "Same dataset with additional fairness re-weighting.",
        },
    ],
    "demo-medical-triage-v1": [
        {
            "system_id": "demo-medical-triage-v1",
            "commit_ref": "v1.1.0-demo",
            "intended_purpose": (
                "Supports emergency-department triage nurses in prioritising "
                "patient queues based on vital signs and symptom inputs."
            ),
            "provider_name": "Demo Tenant — Healthcare Division",
            "training_data_description": (
                "De-identified ED encounter data from three NHS Trust hospitals, "
                "2019-2022."
            ),
        }
    ],
}


def dossier_ingest_metadata(system_id: str, commit_ref: str, idx: int = 0) -> dict:
    """Return the ProIngestDossierRequest payload for a given system dossier."""
    manifest = DOSSIER_MANIFESTS[system_id][idx]
    commit_ref = manifest.get("commit_ref", f"v-demo-{idx}")
    bundle_seed = f"{system_id}-dossier-{idx}-{commit_ref}"
    now = datetime.now(tz=UTC).isoformat()
    return {
        "system_id": system_id,
        "policy_bundle_version": commit_ref,
        "bundle_checksum": _sha256(bundle_seed),
        "size_bytes": len(str(manifest)),
        "signed_by": "demo-signing-key",
        "timestamp": now,
    }
