"""Gap candidates read from declarations in the manifest (no I/O).

A declaration is the provider's own statement, never verified here, so a
manifest row is PARTIAL at most and is never MET.
"""

from __future__ import annotations

from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    GapStatus,
    ImportedPackEvidence,
    SystemManifest,
)

MANIFEST_SOURCE_REFS: frozenset[str] = frozenset(
    {
        "human_oversight_declaration",
        "record_keeping_declaration",
        "imported_provider_pack",
    }
)

# E-15: wording and the PARTIAL ceiling are the founder's/lawyer's to approve.
NEEDS_REVIEW_NOTES: dict[str, dict] = {
    "human_oversight_declaration": {
        "source": (
            "Regulation (EU) 2024/1689 Art. 14; manifest declaration, "
            "not independently verified"
        ),
        "confidence": "low",
        "needs_founder_review": True,
        "note": (
            "A structured declaration reads PARTIAL at most and Art. 14 is "
            "never MET from it; the ceiling and the row wording need approval."
        ),
    },
    # Literal, not an import of dossier_generator (cycle); a test keeps the two equal.
    "record_keeping_declaration": {
        "source": "Regulation (EU) 2024/1689 Art. 12; manifest declaration",
        "confidence": "low",
        "needs_founder_review": True,
        "note": (
            "A declaration reads PARTIAL at most (MISSING when logging is "
            "declared off) and Art. 12 is never MET from it; the ceiling and "
            "the row wording need approval."
        ),
    },
    "imported_provider_pack": {
        "source": (
            "Regulation (EU) 2024/1689 Art. 26 (text unverified here); "
            "provider-supplied deployer pack recorded by `deployer-pack "
            "import`, not verified by the deployer"
        ),
        "confidence": "low",
        "needs_founder_review": True,
        "note": (
            "A received pack reads PARTIAL at most and Art. 26 is never MET "
            "from it; a verified and an unsigned pack both read PARTIAL; the "
            "ceiling and the row wording need approval."
        ),
    },
}


def _oversight_row(manifest: SystemManifest) -> ArticleGapStatus | None:
    block = manifest.human_oversight
    if block is None:
        return None  # the legacy human_oversight_measures list is never read
    n = len(block.roles)
    can = sum(r.can_intervene for r in block.roles)
    rationale = (
        f"Human oversight declared in the manifest: {n} role(s), {can} with "
        "authority to intervene, escalation path "
        f"{'declared' if block.escalation else 'not declared'}, "
        f"{len(block.evidence_refs)} evidence reference(s). A declaration "
        "only; not verified against the system."
    )
    if not can:
        rationale += " No declared role can intervene."
    return ArticleGapStatus(
        article="",
        status=GapStatus.PARTIAL,  # never MET: a declaration is not evidence
        source=ArticleGapSource.MANIFEST,
        evidence_ref="manifest:human_oversight_declaration",
        rationale=rationale,
        confidence=None,
        confidence_label=ConfidenceLabel.NOT_ASSESSED,
    )


def _imported_pack_row(manifest: SystemManifest) -> ArticleGapStatus | None:
    packs = [
        e
        for e in manifest.imported_evidence.values()
        if isinstance(e, ImportedPackEvidence)
    ]
    if not packs:
        return None
    unsigned = sum(p.verification == "unsigned" for p in packs)
    return ArticleGapStatus(
        article="",
        status=GapStatus.PARTIAL,  # never MET: the provider's own statement
        source=ArticleGapSource.MANIFEST,
        evidence_ref="manifest:imported_provider_pack",
        rationale=(
            f"{len(packs)} deployer pack(s) received from a provider, {unsigned} "
            "unsigned; provider-supplied, not verified by the deployer. "
            "A record of receipt only; not verified against the system."
        ),
        confidence=None,
        confidence_label=ConfidenceLabel.NOT_ASSESSED,
    )


def manifest_gap_status(ref: str, manifest: SystemManifest) -> ArticleGapStatus | None:
    """The row for a manifest source ref, or None (unknown ref or not declared)."""
    if ref == "record_keeping_declaration":
        from opencomplai_core.dossier_generator import record_keeping_gap_status

        return record_keeping_gap_status(manifest)
    if ref == "human_oversight_declaration":
        return _oversight_row(manifest)
    if ref == "imported_provider_pack":
        return _imported_pack_row(manifest)
    return None


def oversight_warnings(manifest: SystemManifest) -> list[str]:
    """Advisory warnings for a declared block; empty when there is none."""
    block = manifest.human_oversight
    if block is None:
        return []
    out = []
    if not any(r.can_intervene for r in block.roles):
        out.append("human_oversight: no declared role can intervene")
    out += [
        f"human_oversight: role {r.role!r} has no training_ref"
        for r in block.roles
        if not r.training_ref
    ]
    return out
