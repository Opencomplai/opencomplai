"""Signed, offline-verifiable deployer pack.

A pack wraps the Art. 13(3) instructions-for-use document (`content`, opaque
here) with a completeness count and an integrity block: the SHA-256 of the
canonical body (everything except `integrity`) and, when a key is given, an
Ed25519 signature over those same bytes under `SigningDomain.DEPLOYER_PACK`.
The public key is never embedded: a self-carried key would make the signature
self-attesting, so the verifier supplies it.

Packs are generated offline and never uploaded. Only `PackIssuance` metadata
(hash, date, signer key id, two counts) reaches the artifact `summaries.packs`.

No clock and no random ids in this module (E-14): `issued_on` is supplied by the
caller, so the same inputs always give the same bytes.

needs_founder_review: true (E-15). The `signer_key_id` is the first 16 hex of the
SHA-256 of the public-key PEM, the same fingerprint `keys rotate` prints.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from opencomplai_core.models import ScanStatusArtifact
from opencomplai_core.signing import (
    SigningDomain,
    canonical_json_bytes,
    resolve_key,
    sign_bundle_bytes,
    verify_bundle_bytes,
)
from opencomplai_core.summaries import (
    ArtifactSummaries,
    PackIssuance,
    PackKind,
    PacksSummary,
)

SCHEMA_ID = "https://schemas.opencomplai.dev/deployer_pack/v1"
PACK_GLOB = "deployer_pack_*.json"
_MAX_PACK_BYTES = 2 * 1024 * 1024
_MAX_ITEMS = 50

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Day = Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PackCompleteness(_Closed):
    items_total: int = Field(ge=0)
    items_provided: int = Field(ge=0)
    items_not_captured: int = Field(ge=0)
    not_captured_items: list[str]


class PackIntegrity(_Closed):
    pack_sha256: Sha256
    signature: str | None = None
    signer_key_id: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")] | None = None


class DeployerPack(_Closed):
    schema_version: Literal["1"] = "1"
    kind: Literal["deployer_pack"] = "deployer_pack"
    system_id: str
    issued_on: Day
    generator_version: str
    content: dict[str, Any]
    completeness: PackCompleteness
    integrity: PackIntegrity


@dataclass(frozen=True)
class PackVerification:
    status: str  # "verified" | "unsigned" | "invalid"
    detail: str


def _body_hash(body: dict[str, Any]) -> tuple[bytes, str]:
    data = canonical_json_bytes(body)
    return data, hashlib.sha256(data).hexdigest()


def _completeness(content: dict[str, Any]) -> PackCompleteness:
    """From the instructions document's own per-point `populated` flags."""
    raw = content.get("points")
    if not isinstance(raw, list) or not all(
        isinstance(p, dict) and isinstance(p.get("populated"), bool) for p in raw
    ):
        raise ValueError(
            "content is not an instructions-for-use document: "
            "`points` must be a list of points with a boolean `populated`"
        )
    points = raw
    missing = [str(p.get("point", "")) for p in points if not p.get("populated")]
    return PackCompleteness(
        items_total=len(points),
        items_provided=len(points) - len(missing),
        items_not_captured=len(missing),
        not_captured_items=missing,
    )


def _key_id(private_pem: bytes) -> str:
    from opencomplai_core.acceptance import public_key_pem_from_private

    pub = public_key_pem_from_private(private_pem)
    return hashlib.sha256(pub.encode("utf-8")).hexdigest()[:16]


def build_pack(
    content: dict[str, Any],
    *,
    system_id: str,
    issued_on: str,
    generator_version: str,
    private_key_path: Path | None = None,
) -> DeployerPack:
    """Seal `content`. Signed only when `private_key_path` (or the env key) is given."""
    pack = DeployerPack(
        system_id=system_id,
        issued_on=issued_on,
        generator_version=generator_version,
        content=content,
        completeness=_completeness(content),
        integrity=PackIntegrity(pack_sha256="0" * 64),
    )
    body = pack.model_dump(mode="json", exclude={"integrity"})
    data, digest = _body_hash(body)
    signature = signer = None
    if private_key_path is not None:
        signature = sign_bundle_bytes(
            data, private_key_path, SigningDomain.DEPLOYER_PACK
        )
        signer = _key_id(resolve_key(private_key_path))
    return pack.model_copy(
        update={
            "integrity": PackIntegrity(
                pack_sha256=digest, signature=signature, signer_key_id=signer
            )
        }
    )


def verify_pack(
    pack_dict: dict[str, Any], public_key_path: Path | None = None
) -> PackVerification:
    """Hash first, then (when signed) the signature under the deployer-pack domain."""
    integrity = pack_dict.get("integrity")
    if not isinstance(integrity, dict):
        return PackVerification("invalid", "missing integrity block")
    body = {k: v for k, v in pack_dict.items() if k != "integrity"}
    data, digest = _body_hash(body)
    if digest != integrity.get("pack_sha256"):
        return PackVerification("invalid", "content hash mismatch")
    signature = integrity.get("signature")
    # Must come before verify_bundle_bytes: it cannot tell unsigned from tampered.
    if signature is None:
        return PackVerification("unsigned", "hash matches, no signature present")
    if public_key_path is None:
        return PackVerification("invalid", "public key needed to verify signature")
    try:
        ok = verify_bundle_bytes(
            data, signature, public_key_path, SigningDomain.DEPLOYER_PACK
        )
        pub_pem = public_key_path.read_bytes()
    except Exception:
        return PackVerification("invalid", "malformed signature or public key")
    if not ok:
        return PackVerification("invalid", "signature does not match")
    claimed = integrity.get("signer_key_id")
    if claimed is not None and claimed != hashlib.sha256(pub_pem).hexdigest()[:16]:
        return PackVerification("invalid", "signer_key_id does not match public key")
    return PackVerification("verified", "hash and signature match")


def deployer_pack_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        **DeployerPack.model_json_schema(),
    }


def write_schemas(core_path: Path, vendored_path: Path) -> None:
    """Regenerate the core schema and its vendored copy (LF, sorted keys)."""
    text = json.dumps(deployer_pack_schema(), indent=2, sort_keys=True) + "\n"
    for path in (core_path, vendored_path):
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def build_packs_summary(pack_dir: Path) -> PacksSummary | None:
    """Metadata of the intact packs in `pack_dir`; None when there are none."""
    found: dict[str, PackIssuance] = {}
    for path in sorted(pack_dir.glob(PACK_GLOB)) if pack_dir.is_dir() else []:
        try:
            if path.stat().st_size > _MAX_PACK_BYTES:
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            pack = DeployerPack.model_validate(raw)
        except (OSError, ValueError, ValidationError):
            continue
        if _body_hash({k: v for k, v in raw.items() if k != "integrity"})[1] != (
            pack.integrity.pack_sha256
        ):
            continue
        found[pack.integrity.pack_sha256] = PackIssuance(
            pack_sha256=pack.integrity.pack_sha256,
            issued_on=pack.issued_on,
            kind=PackKind.DEPLOYER,
            signer_key_id=pack.integrity.signer_key_id,
            items_provided=pack.completeness.items_provided,
            items_not_captured=pack.completeness.items_not_captured,
        )
    if not found:
        return None
    items = sorted(
        found.values(), key=lambda i: (i.issued_on, i.pack_sha256), reverse=True
    )
    return PacksSummary(issued=len(items), items=items[:_MAX_ITEMS])


def with_pack_summary(
    artifact: ScanStatusArtifact, pack_dir: Path
) -> ScanStatusArtifact:
    """Set `summaries.packs`, keeping any other sub-object; unchanged without packs."""
    packs = build_packs_summary(pack_dir)
    if packs is None:
        return artifact
    summaries = (artifact.summaries or ArtifactSummaries()).model_copy(
        update={"packs": packs}
    )
    return artifact.model_copy(update={"summaries": summaries})
