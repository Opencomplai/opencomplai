"""The neutral evidence package is a pure, free-text-free function of an artifact."""

from __future__ import annotations

import csv
import io
import json

import pytest
from opencomplai_core.evidence_package import (
    build_evidence_package,
    package_to_csv,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
    ScanResult,
    ScanStatusArtifact,
)

_MARKER = "SECRET-RATIONALE-TEXT"


def _raw(system_id: str = "sys-1", **over: object) -> dict:
    art = ScanStatusArtifact(
        install_id="i",
        system_id=system_id,
        commit_ref="abc1234",
        result=ScanResult.CONTROL_FAIL,
        failed_controls=["C-1"],
        evidence_hashes=["a" * 64],
        rationale_hash="0" * 64,
        duration_ms=5,
        pending_verifications_count=2,
        rule_set_version="2026.10",
        cli_version="0.9.1",
        manifest_sha256="b" * 64,
        timestamp="2026-10-06T00:00:00+00:00",
        gap_report=GapReport(
            system_id=system_id,
            commit_ref="abc1234",
            generated_at="2026-10-06T00:00:00+00:00",
            articles=[
                ArticleGapStatus(
                    article="Art. 9",
                    status=GapStatus.MISSING,
                    source=ArticleGapSource.RULE,
                    evidence_ref="R-9",
                    rationale=_MARKER,
                    confidence=0.5,
                ),
                ArticleGapStatus(
                    article="Art. 10",
                    status=GapStatus.MET,
                    source=ArticleGapSource.EVALUATOR,
                    evidence_ref="none",
                ),
            ],
        ),
    )
    return {**json.loads(art.model_dump_json()), **over}


def test_build_copies_fields_and_drops_rationale() -> None:
    raw = _raw()
    pkg = build_evidence_package(raw)
    assert pkg.package_version == "1"
    assert pkg.identity.system_id == "sys-1"
    assert pkg.identity.manifest_sha256 == "b" * 64
    assert pkg.provenance.rule_set_version == "2026.10"
    assert pkg.provenance.policy_bundle_version is None
    assert pkg.verdict.result == ScanResult.CONTROL_FAIL
    assert pkg.verdict.failed_controls == ["C-1"]
    assert pkg.verdict.pending_verifications_count == 2
    assert [a.article for a in pkg.articles] == ["Art. 9", "Art. 10"]
    assert pkg.articles[0].confidence == 0.5
    assert pkg.evidence_hashes == ["a" * 64]
    assert pkg.verification.signed is False
    assert pkg.artifact == raw
    extracted = pkg.model_dump_json(exclude={"artifact"})
    assert _MARKER not in extracted
    assert "rationale" not in extracted


def test_build_rejects_artifact_without_gap_report() -> None:
    raw = _raw()
    raw["gap_report"] = None
    with pytest.raises(ValueError, match="no gap_report"):
        build_evidence_package(raw)
    with pytest.raises(ValueError, match="not a compliance artifact"):
        build_evidence_package({"hello": "world"})


def test_tree_fields_are_null_when_absent_and_copied_when_present() -> None:
    pkg = build_evidence_package(_raw())
    assert pkg.identity.tree_sha256 is None
    assert pkg.identity.tree_dirty is None
    pkg = build_evidence_package(_raw(tree_sha256="c" * 64, tree_dirty=True))
    assert pkg.identity.tree_sha256 == "c" * 64
    assert pkg.identity.tree_dirty is True
    # A wrong type is not an artifact; it is never coerced into the package.
    with pytest.raises(ValueError, match="tree_sha256"):
        build_evidence_package(_raw(tree_sha256=7))


def test_csv_formula_cells_are_neutralised() -> None:
    pkg = build_evidence_package(_raw(system_id='=HYPERLINK("x")'))
    rows = list(csv.reader(io.StringIO(package_to_csv(pkg))))
    assert rows[1][0] == '\'=HYPERLINK("x")'
    for lead in ("+", "-", "@", "\t", "\r"):
        pkg = build_evidence_package(_raw(system_id=f"{lead}1"))
        got = list(csv.reader(io.StringIO(package_to_csv(pkg), newline="")))
        assert got[1][0] == f"'{lead}1"


def test_package_is_deterministic() -> None:
    raw = _raw()
    a = build_evidence_package(raw)
    b = build_evidence_package(raw)
    assert a.model_dump_json() == b.model_dump_json()
    assert package_to_csv(a) == package_to_csv(b)
    assert package_to_csv(a).count("\n") == 3  # header and two rows, LF only
    assert "\r" not in package_to_csv(a)
    # The package holds a copy: changing it never changes the input.
    a.artifact["system_id"] = "changed"
    assert raw["system_id"] == "sys-1"
