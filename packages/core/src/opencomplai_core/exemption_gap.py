"""Gap row and opt-in gate for the Art. 6(3) exemption record.

A provider whose checker session relies on the Art. 6(3) derogation (the engine
lists ``provider_art_6_4_registration`` for providers only) is expected to hold a
signed ``art_6_3_exemption`` record. This module reports whether one is valid:

* ``exemption_record_status`` is the ``record`` source of the ``Art. 49`` gap
  article (``gap_article_map.json``). A valid record reads MET; any other state
  reads MISSING with the state name only, never record content.
* ``apply_exemption_gate`` is the opt-in ``check --require-exemption-record``
  gate: a missing or stale record becomes the failed control
  ``EU_AIA_ART6_3_EXEMPTION_RECORD``. Without the flag the artifact is untouched.

The record is the provider's own declaration of the grounds it relied on. Nothing
here assesses whether the exemption is valid.

Known ceiling: the record source is listed first on ``Art. 49`` and worst status
wins with a tie keeping the earlier source, so a registration-probe MISSING is
hidden behind a record MISSING until the record is valid. A valid record cannot
lift the row to Met: the registration probe still decides it.

Pure module: no clock, no network. Reads ``repo_root`` and the trusted-key
environment variable only, never the home directory.
"""

from __future__ import annotations

import os
from pathlib import Path

from opencomplai_core.acceptance import (
    ART_6_3_EXEMPTION,
    evaluate_record,
    record_path,
    trusted_key_ids_from_env,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    GapStatus,
    ScanResult,
    ScanStatusArtifact,
    SystemManifest,
)

CONTROL_ID = "EU_AIA_ART6_3_EXEMPTION_RECORD"
RECORD_REF = "art_6_3_exemption_record"
DEROGATION_OBLIGATION = "provider_art_6_4_registration"

# Flagged data (E-1, E-9): the gate and row wording below is product design.
PROVENANCE = {
    "source": "product design, no external citation",
    "confidence": "low",
    "needs_founder_review": True,
}

_DECLARATION = (
    "The record is the provider's own declaration of the grounds it relied on; "
    "this row does not assess whether the exemption is valid."
)


def relies_on_derogation(manifest: SystemManifest) -> bool:
    """True when the recorded checker session lists the Art. 6(4) registration."""
    session = manifest.checker_session
    return session is not None and DEROGATION_OBLIGATION in session.obligation_ids


def exemption_record_status(
    manifest: SystemManifest, repo_root: Path
) -> ArticleGapStatus:
    """MET for a valid signed record, else MISSING naming the record state."""
    root = repo_root.resolve()
    status = evaluate_record(
        record_path(root, manifest.system_id, ART_6_3_EXEMPTION),
        manifest,
        ART_6_3_EXEMPTION,
        trusted_key_ids=trusted_key_ids_from_env(os.environ),
    )
    if status.state == "valid":
        return ArticleGapStatus(
            article="",
            status=GapStatus.MET,
            source=ArticleGapSource.ARTIFACT,
            evidence_ref=RECORD_REF,
            rationale=f"Art. 6(3) exemption record is valid. {_DECLARATION}",
            confidence=None,
            confidence_label=ConfidenceLabel.ATTESTED,
        )
    return ArticleGapStatus(
        article="",
        status=GapStatus.MISSING,
        source=ArticleGapSource.ARTIFACT,
        evidence_ref=RECORD_REF,
        rationale=(
            f"The checker session relies on the Art. 6(3) derogation, but the "
            f"exemption record is {status.state}. {_DECLARATION}"
        ),
        confidence=None,
        confidence_label=ConfidenceLabel.NOT_ASSESSED,
    )


def apply_exemption_gate(
    artifact: ScanStatusArtifact,
    manifest: SystemManifest,
    *,
    repo_root: Path,
    require: bool,
) -> ScanStatusArtifact:
    """Fail the check for a missing or stale record, only when ``require`` is set.

    PASS becomes CONTROL_FAIL. POLICY_BLOCK, VALIDATION_FAIL, DEGRADED_COMPLETE
    and TRAP_DETECTED keep their result and do not gain the control id. Never
    halts.
    """
    if (
        not require
        or not relies_on_derogation(manifest)
        or artifact.result not in (ScanResult.PASS, ScanResult.CONTROL_FAIL)
        or exemption_record_status(manifest, repo_root).status == GapStatus.MET
    ):
        return artifact
    return artifact.model_copy(
        update={
            "result": ScanResult.CONTROL_FAIL,
            "failed_controls": list(
                dict.fromkeys([*artifact.failed_controls, CONTROL_ID])
            ),
        }
    )
