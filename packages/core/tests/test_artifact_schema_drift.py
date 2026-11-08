"""data/scan_status_artifact.schema.json, data/gap_report.schema.json,
data/evidence_package.schema.json and data/attestation_bundle.schema.json
are generated from the pydantic models (scripts/generate_artifact_schemas.py).
Regenerate after editing ScanStatusArtifact, GapReport, EvidencePackage,
AttestationBundle or any model they embed.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from opencomplai_core.json_schemas import (
    ARTIFACT_SCHEMA_ID,
    ATTESTATION_BUNDLE_SCHEMA_ID,
    EVIDENCE_PACKAGE_SCHEMA_ID,
    GAP_REPORT_SCHEMA_ID,
    SCHEMA_VERSION,
    build_artifact_schema,
    build_attestation_bundle_schema,
    build_evidence_package_schema,
    build_gap_report_schema,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    AttestationBundleRef,
    AttestationBundleUnavailable,
    GapReport,
    GapStatus,
    ScanResult,
    ScanStatusArtifact,
)
from pydantic import ValidationError

_CORE = Path(__file__).resolve().parents[1]
_DATA = _CORE / "src" / "opencomplai_core" / "data"
_ARTIFACT = _DATA / "scan_status_artifact.schema.json"
_GAP = _DATA / "gap_report.schema.json"
_PACKAGE = _DATA / "evidence_package.schema.json"
_BUNDLE = _DATA / "attestation_bundle.schema.json"
_DASHBOARD = _CORE.parents[1] / "dashboard-saas" / "schemas"
_FIX = "run `python scripts/generate_artifact_schemas.py` and commit the result."


def _load(path: Path) -> dict:
    assert path.is_file(), f"{path} is missing - {_FIX}"
    return json.loads(path.read_text(encoding="utf-8"))


def _minimal(**over: object) -> dict:
    base = {
        "install_id": "i",
        "system_id": "s",
        "commit_ref": "abc1234",
        "result": "pass",
        "rationale_hash": "0" * 64,
        "duration_ms": 5,
    }
    return {**base, **over}


def test_artifact_schema_matches_model() -> None:
    assert _load(_ARTIFACT) == build_artifact_schema(), (
        f"artifact schema drifted - {_FIX}"
    )


def test_gap_report_schema_matches_model() -> None:
    assert _load(_GAP) == build_gap_report_schema(), (
        f"gap report schema drifted - {_FIX}"
    )


def test_evidence_package_schema_matches_model() -> None:
    assert _load(_PACKAGE) == build_evidence_package_schema(), (
        f"evidence package schema drifted - {_FIX}"
    )


def test_attestation_bundle_schema_matches_model() -> None:
    assert _load(_BUNDLE) == build_attestation_bundle_schema(), (
        f"attestation bundle schema drifted - {_FIX}"
    )


def test_ids_and_version() -> None:
    for path, schema_id in (
        (_ARTIFACT, ARTIFACT_SCHEMA_ID),
        (_GAP, GAP_REPORT_SCHEMA_ID),
        (_PACKAGE, EVIDENCE_PACKAGE_SCHEMA_ID),
        (_BUNDLE, ATTESTATION_BUNDLE_SCHEMA_ID),
    ):
        doc = _load(path)
        assert doc["$id"] == schema_id
        assert doc["schema_version"] == SCHEMA_VERSION == "1"
        assert doc["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert (
        ARTIFACT_SCHEMA_ID == "https://schemas.opencomplai.dev/scan_status_artifact/v1"
    )
    assert GAP_REPORT_SCHEMA_ID == "https://schemas.opencomplai.dev/gap_report/v1"
    assert (
        EVIDENCE_PACKAGE_SCHEMA_ID
        == "https://schemas.opencomplai.dev/evidence_package/v1"
    )
    assert (
        ATTESTATION_BUNDLE_SCHEMA_ID
        == "https://schemas.opencomplai.dev/attestation_bundle/v1"
    )


def test_sample_artifact_validates() -> None:
    schema = _load(_ARTIFACT)
    gap = GapReport(
        system_id="s",
        commit_ref="abc1234",
        generated_at="2026-10-06T00:00:00+00:00",
        articles=[
            ArticleGapStatus(
                article="Art. 6",
                status=GapStatus.MET,
                source=ArticleGapSource.RULE,
                evidence_ref="R-1",
            )
        ],
    )
    full = ScanStatusArtifact(
        install_id="i",
        system_id="s",
        commit_ref="abc1234",
        result=ScanResult.PASS,
        rationale_hash="0" * 64,
        duration_ms=5,
        gap_report=gap,
    )
    jsonschema.validate(json.loads(full.model_dump_json()), schema)
    jsonschema.validate(_minimal(), schema)


def test_bad_artifact_rejected() -> None:
    schema = _load(_ARTIFACT)
    no_hash = _minimal()
    del no_hash["rationale_hash"]
    for bad in (no_hash, _minimal(result="nope")):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


def test_schema_ids_unique_across_core_and_dashboard() -> None:
    # Skipped only where dashboard-saas is absent (the public projection).
    if not _DASHBOARD.is_dir():
        pytest.skip("dashboard-saas/schemas absent (public projection)")
    ids: list[str] = []
    for d in (_DATA, _DASHBOARD):
        for p in sorted(d.glob("*.schema.json")):
            # A vendored copy of a core schema (deployer_pack) repeats its $id on purpose.
            if d is _DASHBOARD and (_DATA / p.name).is_file():
                continue
            doc = json.loads(p.read_text(encoding="utf-8"))
            if "$id" in doc:
                ids.append(doc["$id"])
    assert len(ids) == len(set(ids)), f"duplicate $id in {ids}"
    dash_id = json.loads(
        (_DASHBOARD / "first_scan_status.schema.json").read_text(encoding="utf-8")
    )["$id"]
    assert dash_id not in (
        ARTIFACT_SCHEMA_ID,
        GAP_REPORT_SCHEMA_ID,
        EVIDENCE_PACKAGE_SCHEMA_ID,
    )


# --- attestation_bundle: the optional artifact block ---------------------------

_SHA = "0" * 64
_REF = {
    "sha256": _SHA,
    "signature": "QUJD",
    "key_id": "dash-2026-11",
    "issued_at": "2026-11-03T09:30:00+00:00",
    "count": 3,
}
_UNAVAILABLE = {"status": "unavailable", "reason": "fetch_failed"}


def test_artifact_without_a_bundle_is_unchanged() -> None:
    artifact = ScanStatusArtifact(
        install_id="i",
        system_id="s",
        commit_ref="abc1234",
        result=ScanResult.PASS,
        rationale_hash=_SHA,
        duration_ms=5,
    )
    assert "attestation_bundle" not in artifact.model_dump()
    assert "attestation_bundle" not in json.loads(artifact.model_dump_json())
    assert artifact.model_dump_json() == (
        '{"install_id":"i","system_id":"s","commit_ref":"abc1234","result":"pass",'
        '"failed_controls":[],"evidence_hashes":[],'
        f'"rationale_hash":"{_SHA}","duration_ms":5,'
        '"pending_verifications_count":0,"signature":null,"eval_summary":null,'
        '"scan_summary":null,"gap_report":null,"nist_rmf_report":null,'
        '"controls":null}'
    )


@pytest.mark.parametrize("block", [_REF, _UNAVAILABLE])
def test_artifact_schema_accepts_both_bundle_shapes(block: dict) -> None:
    schema = _load(_ARTIFACT)
    jsonschema.validate(_minimal(attestation_bundle=block), schema)
    artifact = ScanStatusArtifact.model_validate(_minimal(attestation_bundle=block))
    assert isinstance(
        artifact.attestation_bundle,
        (AttestationBundleRef, AttestationBundleUnavailable),
    )
    dumped = json.loads(artifact.model_dump_json())
    assert dumped["attestation_bundle"] == block
    jsonschema.validate(dumped, schema)


@pytest.mark.parametrize(
    "block",
    [
        {**_REF, "extra": 1},
        {**_UNAVAILABLE, "extra": 1},
        {**_REF, "status": "unavailable"},
        {**_UNAVAILABLE, "sha256": _SHA},
        {**_REF, "sha256": "ABC"},
        {**_REF, "count": -1},
        {k: v for k, v in _REF.items() if k != "key_id"},
        {"status": "unavailable"},
        {"status": "unavailable", "reason": "Fetch failed: http://x"},
        {"status": "gone", "reason": "fetch_failed"},
    ],
)
def test_artifact_schema_rejects_bad_bundle_blocks(block: dict) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_minimal(attestation_bundle=block), _load(_ARTIFACT))
    with pytest.raises(ValidationError):
        ScanStatusArtifact.model_validate(_minimal(attestation_bundle=block))


def test_bundle_schema_is_closed_and_validates_a_bundle() -> None:
    schema = _load(_BUNDLE)
    bundle = {
        "schema_version": "attestation_bundle/v1",
        "system_id": None,
        "issued_at": "2026-11-03T09:30:00+00:00",
        "attestations": {
            "ISO_IEC_27001": {
                "ISO_IEC_27001:A.6.3": {
                    "statement": "s",
                    "attested_by": "Jane Doe",
                    "attested_at": "2026-06-01",
                    "valid_until": "2027-06-01",
                    "record_id": "rec_1",
                    "evidence": [{"kind": "file", "ref": "t.pdf", "sha256": _SHA}],
                }
            }
        },
        "excluded": {},
        "key_id": "dash-2026-11",
        "signature": "QUJD",
    }
    jsonschema.validate(bundle, schema)
    for bad in (
        {**bundle, "extra": 1},
        {**bundle, "schema_version": "attestation_bundle/v2"},
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)
    for path, node in _objects(schema):
        assert node.get("additionalProperties") is False, path


def _objects(node: object, path: str = ""):
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            yield path, node
        for key, value in node.items():
            yield from _objects(value, f"{path}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _objects(value, f"{path}/{i}")


# --- the ingest copy of the scan schema must carry the same block --------------

_INGEST_BASE = {
    "system_id": "s",
    "commit_ref": "abc1234",
    "policy_bundle_version": "v1",
    "result": "pass",
    "timestamp": "2026-11-03T00:00:00Z",
}
_BLOCK_DEFS = ("AttestationBundleRef", "AttestationBundleUnavailable")


def _ingest_schema() -> dict:
    # Skipped only where dashboard-saas is absent (the public projection).
    if not _DASHBOARD.is_dir():
        pytest.skip("dashboard-saas/schemas absent (public projection)")
    return _load(_DASHBOARD / "first_scan_status.schema.json")


@pytest.mark.parametrize("block", [_REF, _UNAVAILABLE, None])
def test_ingest_schema_accepts_the_bundle_block(block: dict | None) -> None:
    jsonschema.validate({**_INGEST_BASE, "attestation_bundle": block}, _ingest_schema())


@pytest.mark.parametrize(
    "block",
    [
        {**_REF, "extra": 1},
        {**_UNAVAILABLE, "extra": 1},
        {**_REF, "sha256": "ABC"},
        {**_REF, "signature": "not base64!"},
        {**_REF, "key_id": "x" * 65},
        {**_REF, "issued_at": "yesterday"},
        {**_REF, "count": 1_000_001},
        {"status": "unavailable"},
        {"status": "unavailable", "reason": "Fetch failed: http://x"},
        {"status": "gone", "reason": "fetch_failed"},
        "unavailable",
    ],
)
def test_ingest_schema_rejects_bad_bundle_blocks(block: object) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {**_INGEST_BASE, "attestation_bundle": block}, _ingest_schema()
        )


def test_ingest_bundle_defs_are_closed_and_bounded() -> None:
    schema = _ingest_schema()
    for name in _BLOCK_DEFS:
        node = schema["$defs"][name]
        assert node["additionalProperties"] is False, name
        for prop, rule in node["properties"].items():
            if rule["type"] == "string":
                assert "maxLength" in rule, f"{name}.{prop}"
                assert "pattern" in rule or "enum" in rule, f"{name}.{prop}"
    assert "attestation_bundle" not in schema["required"]


def test_a_schema_without_the_property_rejects_the_block() -> None:
    # Why the ingest service deploys before any CLI that emits the block:
    # the closed schema an older ingest still has refuses the unknown key.
    old = _ingest_schema()
    del old["properties"]["attestation_bundle"]
    jsonschema.validate(_INGEST_BASE, old)
    with pytest.raises(jsonschema.ValidationError, match="attestation_bundle"):
        jsonschema.validate({**_INGEST_BASE, "attestation_bundle": _REF}, old)
