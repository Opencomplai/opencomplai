"""data/scan_status_artifact.schema.json and data/gap_report.schema.json are
generated from the pydantic models (scripts/generate_artifact_schemas.py).
Regenerate after editing ScanStatusArtifact, GapReport or any model they embed.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from opencomplai_core.json_schemas import (
    ARTIFACT_SCHEMA_ID,
    GAP_REPORT_SCHEMA_ID,
    SCHEMA_VERSION,
    build_artifact_schema,
    build_gap_report_schema,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
    ScanResult,
    ScanStatusArtifact,
)

_CORE = Path(__file__).resolve().parents[1]
_DATA = _CORE / "src" / "opencomplai_core" / "data"
_ARTIFACT = _DATA / "scan_status_artifact.schema.json"
_GAP = _DATA / "gap_report.schema.json"
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


def test_ids_and_version() -> None:
    for path, schema_id in (
        (_ARTIFACT, ARTIFACT_SCHEMA_ID),
        (_GAP, GAP_REPORT_SCHEMA_ID),
    ):
        doc = _load(path)
        assert doc["$id"] == schema_id
        assert doc["schema_version"] == SCHEMA_VERSION == "1"
        assert doc["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert (
        ARTIFACT_SCHEMA_ID == "https://schemas.opencomplai.dev/scan_status_artifact/v1"
    )
    assert GAP_REPORT_SCHEMA_ID == "https://schemas.opencomplai.dev/gap_report/v1"


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
    assert dash_id not in (ARTIFACT_SCHEMA_ID, GAP_REPORT_SCHEMA_ID)
