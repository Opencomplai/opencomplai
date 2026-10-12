"""Neutral evidence package: one versioned JSON file (plus a flat CSV) that a
governance tool can read without knowing the OpenComplAI model.

The package carries a few extracted fields and the original signed artifact
embedded unchanged, so the receiver can re-verify the signature offline. It is
a pure function of the artifact (no clock, no I/O) and it is not signed itself.
Rationale text is never copied into the extracted fields or the CSV.
"""

from __future__ import annotations

import copy
import csv
import io
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from opencomplai_core.models import (
    ArticleGapSource,
    ConfidenceLabel,
    GapStatus,
    ScanResult,
    ScanStatusArtifact,
)

_CSV_HEADER = (
    "system_id",
    "commit_ref",
    "rule_set_version",
    "article",
    "status",
    "source",
    "evidence_ref",
    "confidence",
    "confidence_label",
)
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PackageIdentity(_Strict):
    system_id: str
    commit_ref: str
    manifest_sha256: str | None
    tree_sha256: str | None
    tree_dirty: bool | None
    timestamp: str | None


class PackageProvenance(_Strict):
    cli_version: str | None
    rule_set_version: str | None
    schema_version: str | None
    policy_bundle_version: str | None


class PackageVerdict(_Strict):
    result: ScanResult
    failed_controls: list[str]
    pending_verifications_count: int


class PackageArticle(_Strict):
    article: str
    status: GapStatus
    source: ArticleGapSource
    evidence_ref: str
    confidence: float | None
    confidence_label: ConfidenceLabel


class PackageVerification(_Strict):
    signed: bool
    # Constants: a fixed value, so a receiver can rely on the exact text.
    signature_domain: Literal["scan-status-artifact"] = "scan-status-artifact"
    artifact_pointer: Literal["/artifact"] = "/artifact"
    command: Literal[
        "opencomplai verify <artifact.json> --kind artifact --pub-key <signer-public-key.pem>"
    ] = "opencomplai verify <artifact.json> --kind artifact --pub-key <signer-public-key.pem>"
    note: Literal[
        "The public key must come from the signer, never from this package. "
        "The package itself is not signed; only the embedded artifact is."
    ] = (
        "The public key must come from the signer, never from this package. "
        "The package itself is not signed; only the embedded artifact is."
    )


class EvidencePackage(_Strict):
    package_version: Literal["1"]
    identity: PackageIdentity
    provenance: PackageProvenance
    verdict: PackageVerdict
    articles: list[PackageArticle]
    evidence_hashes: list[str]
    verification: PackageVerification
    artifact: dict[str, Any]


def _opt(raw: dict[str, Any], key: str, kind: type) -> Any:
    value = raw.get(key)
    return value if isinstance(value, kind) else None


def build_evidence_package(artifact: dict[str, Any]) -> EvidencePackage:
    """Build the package from a raw artifact dict. Raises ValueError for a
    non-artifact or an artifact without a gap report."""
    try:
        model = ScanStatusArtifact.model_validate(artifact)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(map(str, err['loc'])) or 'input'}: {err['msg']}"
            for err in e.errors()[:3]
        )
        raise ValueError(f"not a compliance artifact ({problems})") from None
    if model.gap_report is None:
        raise ValueError(
            "artifact has no gap_report; run `opencomplai check --with-gaps`"
        )
    return EvidencePackage(
        package_version="1",
        identity=PackageIdentity(
            system_id=model.system_id,
            commit_ref=model.commit_ref,
            manifest_sha256=model.manifest_sha256,
            tree_sha256=_opt(artifact, "tree_sha256", str),
            tree_dirty=_opt(artifact, "tree_dirty", bool),
            timestamp=model.timestamp,
        ),
        provenance=PackageProvenance(
            cli_version=model.cli_version,
            rule_set_version=model.rule_set_version,
            schema_version=model.schema_version,
            policy_bundle_version=model.policy_bundle_version,
        ),
        verdict=PackageVerdict(
            result=model.result,
            failed_controls=list(model.failed_controls),
            pending_verifications_count=model.pending_verifications_count,
        ),
        articles=[
            PackageArticle(
                article=a.article,
                status=a.status,
                source=a.source,
                evidence_ref=a.evidence_ref,
                confidence=a.confidence,
                confidence_label=a.confidence_label,
            )
            for a in model.gap_report.articles
        ],
        evidence_hashes=list(model.evidence_hashes),
        verification=PackageVerification(signed=bool(model.signature)),
        artifact=copy.deepcopy(artifact),
    )


def _cell(value: object) -> str:
    if value is None:
        return ""
    text = str(getattr(value, "value", value))
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def package_to_csv(pkg: EvidencePackage) -> str:
    """One row per article, LF line endings, formula-guarded cells."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_CSV_HEADER)
    for a in pkg.articles:
        writer.writerow(
            _cell(v)
            for v in (
                pkg.identity.system_id,
                pkg.identity.commit_ref,
                pkg.provenance.rule_set_version,
                a.article,
                a.status,
                a.source,
                a.evidence_ref,
                a.confidence,
                a.confidence_label,
            )
        )
    return buf.getvalue()
