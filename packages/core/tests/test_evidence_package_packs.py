"""Pack rows in the neutral evidence package."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import jsonschema
import opencomplai_core
import pytest
from opencomplai_core.evidence_package import (
    build_evidence_package,
    package_to_csv,
    package_to_json,
    sign_package,
    verify_package,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    FrameworkReport,
    GapReport,
    GapStatus,
    ScanResult,
    ScanStatusArtifact,
)
from opencomplai_core.signing import generate_keypair

_SCHEMA = (
    Path(opencomplai_core.__file__).parent / "data" / "evidence_package.schema.json"
)


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)


def _gap(articles: list[ArticleGapStatus]) -> GapReport:
    return GapReport(
        system_id="sys-1",
        commit_ref="abc1234",
        generated_at="2026-10-06T00:00:00+00:00",
        articles=articles,
    )


def _eu() -> GapReport:
    return _gap(
        [
            ArticleGapStatus(
                article="Art. 9",
                status=GapStatus.MISSING,
                source=ArticleGapSource.RULE,
                evidence_ref="R-9",
            )
        ]
    )


def _raw(with_packs: bool) -> dict:
    reports = {
        "EU_AI_ACT": FrameworkReport(
            framework="EU_AI_ACT",
            label="EU AI Act",
            data_version="a" * 12,
            disclaimer_ref="DISCLAIMER_V1",
            report=_eu(),
        )
    }
    if with_packs:
        reports["TST"] = FrameworkReport(
            framework="TST",
            label="Test pack",
            data_version="b" * 12,
            disclaimer_ref="DISCLAIMER_V2",
            excluded={"TST:R3": "No deployers."},
            report=_gap(
                [
                    ArticleGapStatus(
                        article="TST:R1",
                        status=GapStatus.MET,
                        source=ArticleGapSource.ARTIFACT,
                        evidence_ref="docs/risk_register.md",
                        rationale="SECRET-RATIONALE-TEXT",
                        evidence_class="hybrid",
                        corroborated=True,
                    ),
                    ArticleGapStatus(
                        article="TST:R2",
                        status=GapStatus.MISSING,
                        source=ArticleGapSource.ATTESTATION,
                        evidence_ref="none",
                    ),
                ]
            ),
        )
    art = ScanStatusArtifact(
        install_id="i",
        system_id="sys-1",
        commit_ref="abc1234",
        result=ScanResult.CONTROL_FAIL,
        failed_controls=["C-1"],
        evidence_hashes=["a" * 64],
        rationale_hash="0" * 64,
        duration_ms=5,
        gap_report=_eu(),
        framework_reports=reports,
    )
    return json.loads(art.model_dump_json())


def test_pack_rows_carry_class_and_evidence_reference() -> None:
    pkg = build_evidence_package(_raw(True))
    assert pkg.frameworks is not None
    assert [f.framework for f in pkg.frameworks] == ["TST"]
    fw = pkg.frameworks[0]
    assert (fw.label, fw.data_version) == ("Test pack", "b" * 12)
    assert fw.excluded == {"TST:R3": "No deployers."}
    first, second = fw.rows
    assert (first.id, first.status, first.evidence_class) == (
        "TST:R1",
        GapStatus.MET,
        "hybrid",
    )
    assert first.evidence_ref == "docs/risk_register.md"
    assert first.corroborated is True
    assert second.evidence_class is None
    data = json.loads(package_to_json(pkg))
    jsonschema.validate(data, json.loads(_SCHEMA.read_text(encoding="utf-8")))
    assert "SECRET-RATIONALE-TEXT" not in json.dumps(
        {k: v for k, v in data.items() if k != "artifact"}
    )


def test_csv_gains_pack_rows_only_with_packs() -> None:
    rows = list(
        csv.reader(io.StringIO(package_to_csv(build_evidence_package(_raw(True)))))
    )
    assert rows[0][-3:] == ["framework", "evidence_class", "corroborated"]
    assert rows[1][3] == "Art. 9"
    assert rows[1][-3:] == ["", "", ""]
    by_id = {r[3]: r for r in rows[2:]}
    assert by_id["TST:R1"][-3:] == ["TST", "hybrid", "true"]
    assert by_id["TST:R1"][6] == "docs/risk_register.md"
    assert by_id["TST:R2"][-3:] == ["TST", "", ""]
    plain = list(
        csv.reader(io.StringIO(package_to_csv(build_evidence_package(_raw(False)))))
    )
    assert "framework" not in plain[0]
    assert len(plain) == 2


def test_eu_only_artifact_has_no_frameworks_key_and_signature_verifies(
    tmp_path: Path,
) -> None:
    pkg = build_evidence_package(_raw(False))
    assert pkg.frameworks is None
    assert "frameworks" not in json.loads(package_to_json(pkg))
    generate_keypair(tmp_path)
    priv, pub = tmp_path / "signing.key", tmp_path / "signing.pub"
    signed = sign_package(pkg, priv)
    raw = json.loads(package_to_json(signed))
    assert "frameworks" not in raw
    assert verify_package(raw, pub)[0] == "verified"


def test_signature_covers_pack_rows(tmp_path: Path) -> None:
    generate_keypair(tmp_path)
    priv, pub = tmp_path / "signing.key", tmp_path / "signing.pub"
    raw = json.loads(
        package_to_json(sign_package(build_evidence_package(_raw(True)), priv))
    )
    assert verify_package(raw, pub)[0] == "verified"
    raw["frameworks"][0]["rows"][0]["status"] = "missing"
    assert verify_package(raw, pub)[0] == "invalid"
