"""Neutral evidence package: one versioned JSON file (plus a flat CSV) that a
governance tool can read without knowing the OpenComplAI model.

The package carries a few extracted fields and the original signed artifact
embedded unchanged, so the receiver can re-verify the signature offline. It is
a pure function of the artifact (no clock, no I/O). It is signed only when the
exporter asks for it (``sign_package``); otherwise only the embedded artifact is.
Rationale text is never copied into the extracted fields or the CSV.
"""

from __future__ import annotations

import copy
import csv
import io
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    ValidationError,
    model_serializer,
)

from opencomplai_core.agent_attestation import (
    key_id_for_public_pem,
    public_pem_for_private_pem,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ConfidenceLabel,
    GapStatus,
    ScanResult,
    ScanStatusArtifact,
)
from opencomplai_core.serialization import OMIT_DEFAULT, OMIT_NONE, omit_by_table
from opencomplai_core.signing import (
    SigningDomain,
    canonical_json_bytes,
    resolve_key,
    sign_bundle_bytes,
    verify_bundle_bytes,
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
    "tree_sha256",
    "tree_dirty",
    "signed",
    "verdict",
)
SIGNED_NOTE = (
    "The public key must come from the signer, never from this package. "
    "The package is signed in package_signature; the embedded artifact carries "
    "its own signature."
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
        "The package itself is not signed; only the embedded artifact is.",
        "The public key must come from the signer, never from this package. "
        "The package is signed in package_signature; the embedded artifact carries "
        "its own signature.",
    ] = (
        "The public key must come from the signer, never from this package. "
        "The package itself is not signed; only the embedded artifact is."
    )


class PackageSignature(_Strict):
    algorithm: Literal["ed25519"]
    domain: Literal["evidence-package"]
    signer_key_id: str = Field(pattern=r"^sha256:[0-9a-f]{16}$")
    signature: str  # base64
    command: Literal[
        "opencomplai verify <evidence-package.json> --kind evidence-package "
        "--pub-key <signer-public-key.pem>"
    ] = (
        "opencomplai verify <evidence-package.json> --kind evidence-package "
        "--pub-key <signer-public-key.pem>"
    )


class EvidencePackage(_Strict):
    package_version: Literal["1"]
    identity: PackageIdentity
    provenance: PackageProvenance
    verdict: PackageVerdict
    articles: list[PackageArticle]
    # False when the artifact had no gap report (``articles`` is then empty).
    # Omitted from the serialised package when True, so absent means True.
    gaps_included: bool = True
    evidence_hashes: list[str]
    verification: PackageVerification
    artifact: dict[str, Any]
    # Present only on a package exported with ``--sign``; omitted from the
    # serialised package when None, so an unsigned package keeps its old bytes.
    package_signature: PackageSignature | None = None

    @model_serializer(mode="wrap")
    def _omit_unset_fields(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        return omit_by_table(
            self,
            handler(self),
            {"gaps_included": OMIT_DEFAULT, "package_signature": OMIT_NONE},
        )


def _opt(raw: dict[str, Any], key: str, kind: type) -> Any:
    value = raw.get(key)
    return value if isinstance(value, kind) else None


def build_evidence_package(artifact: dict[str, Any]) -> EvidencePackage:
    """Build the package from a raw artifact dict. Raises ValueError for a
    non-artifact. An artifact without a gap report builds with
    ``gaps_included`` False and no articles."""
    try:
        model = ScanStatusArtifact.model_validate(artifact)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(map(str, err['loc'])) or 'input'}: {err['msg']}"
            for err in e.errors()[:3]
        )
        raise ValueError(f"not a compliance artifact ({problems})") from None
    gaps = model.gap_report
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
            for a in (gaps.articles if gaps is not None else [])
        ],
        gaps_included=gaps is not None,
        evidence_hashes=list(model.evidence_hashes),
        verification=PackageVerification(signed=bool(model.signature)),
        artifact=copy.deepcopy(artifact),
    )


def package_signing_bytes(raw: dict[str, Any]) -> bytes:
    """The bytes that are signed: every value except ``package_signature``."""
    return canonical_json_bytes(
        {k: v for k, v in raw.items() if k != "package_signature"}
    )


def sign_package(pkg: EvidencePackage, key_path: Path) -> EvidencePackage:
    """Return ``pkg`` signed under the ``evidence-package`` domain.

    The verification note is switched to the signed text first, so the signed
    bytes already carry it. Raises ``SigningKeyError`` without a usable key.
    """
    base = pkg.model_copy(
        update={
            "verification": pkg.verification.model_copy(update={"note": SIGNED_NOTE})
        }
    )
    raw = base.model_dump(mode="json", exclude={"package_signature"})
    private_pem = resolve_key(key_path)
    signature = sign_bundle_bytes(
        package_signing_bytes(raw), key_path, SigningDomain.EVIDENCE_PACKAGE
    )
    key_id = key_id_for_public_pem(public_pem_for_private_pem(private_pem))
    return base.model_copy(
        update={
            "package_signature": PackageSignature(
                algorithm="ed25519",
                domain="evidence-package",
                signer_key_id=key_id,
                signature=signature,
            )
        }
    )


def verify_package(raw: dict[str, Any], pub_key_path: Path) -> tuple[str, str]:
    """``("unsigned"|"verified"|"invalid", detail)`` for a package dict as read
    from a file (never a re-dumped model: the signed values are the file's)."""
    sig = raw.get("package_signature")
    if sig is None:  # must come first: a failed verify cannot tell unsigned apart
        return "unsigned", "no package signature present"
    try:
        pub_pem = pub_key_path.read_bytes()
        if sig["signer_key_id"] != key_id_for_public_pem(pub_pem):
            return "invalid", "signer_key_id does not match public key"
        ok = verify_bundle_bytes(
            package_signing_bytes(raw),
            sig["signature"],
            pub_key_path,
            SigningDomain.EVIDENCE_PACKAGE,
        )
    except Exception:
        return "invalid", "malformed signature or public key"
    if ok:
        return "verified", "signature matches"
    return "invalid", "signature does not match"


def package_to_json(pkg: EvidencePackage) -> str:
    """The package as JSON; an unsigned one has no ``package_signature`` key
    (the model serialiser omits it when None)."""
    return pkg.model_dump_json(indent=2) + "\n"


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
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
                pkg.identity.tree_sha256,
                pkg.identity.tree_dirty,
                pkg.verification.signed,
                pkg.verdict.result,
            )
        )
    return buf.getvalue()
