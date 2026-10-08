"""Real artifact probes for Art. 11, 26, 49 and 50 (SU-105).

File presence is never proof of compliance: these rows reach PARTIAL at most.
Refs are read off the live article map so a rename there cannot hide a stub.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.gap_probes import PROBE_PROVENANCE, artifact_gap_status
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import ArticleGapSource, ArticleGapStatus, GapStatus
from opencomplai_core.recommend_engine import render_recommendations

ARTICLES = ("Art. 11", "Art. 26", "Art. 49", "Art. 50")


@pytest.fixture(autouse=True)
def _fresh_map():
    load_gap_article_map.cache_clear()
    yield
    load_gap_article_map.cache_clear()


def _ref(article: str) -> str:
    sources = load_gap_article_map()[article]["sources"]
    return next(s["ref"] for s in sources if s["kind"] == "artifact")


def _row(article: str, root: Path | None) -> ArticleGapStatus:
    return artifact_gap_status(_ref(article), root)


def _gap_row(article: str, root: Path) -> ArticleGapStatus:
    report = build_gap_report("s", "HEAD", repo_root=root)
    return next(r for r in report.articles if r.article == article)


def test_art11_without_dossier_is_missing(tmp_path):
    (tmp_path / "other.json").write_text("{}", encoding="utf-8")
    assert _row("Art. 11", tmp_path).status == GapStatus.MISSING
    assert _gap_row("Art. 11", tmp_path).status == GapStatus.MISSING


def test_art11_dossier_is_partial_and_never_met(tmp_path):
    path = tmp_path / "dossier_abc-123.json"
    path.write_text(
        '{"dossier_id": "abc-123", "bundle_checksum": "deadbeef", "a": 1}',
        encoding="utf-8",
    )
    row = _row("Art. 11", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.6
    assert "never reported Met" in row.rationale
    assert _gap_row("Art. 11", tmp_path).status == GapStatus.PARTIAL

    path.write_text("{}", encoding="utf-8")
    row = _row("Art. 11", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35
    assert row.status != GapStatus.MET


def test_art11_dossier_glob_matches_real_name(tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "dossier_abc-123.json").write_text("{}", encoding="utf-8")
    row = _row("Art. 11", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.evidence_ref == "out/dossier_abc-123.json"


def test_recommend_then_gaps_moves_art50_to_partial(tmp_path):
    before = build_gap_report("s", "HEAD", repo_root=tmp_path)
    assert next(r for r in before.articles if r.article == "Art. 50").status == (
        GapStatus.MISSING
    )
    render_recommendations(before, tmp_path / "fixes", repo_root=tmp_path)
    after = _gap_row("Art. 50", tmp_path)
    assert after.status == GapStatus.PARTIAL
    assert after.source == ArticleGapSource.ARTIFACT
    assert "art50-transparency_middleware" in (after.evidence_ref or "")


def test_art13_notice_is_not_art50_evidence(tmp_path):
    (tmp_path / "art13-transparency_notice.md").write_text("# n\n", encoding="utf-8")
    assert _row("Art. 50", tmp_path).status == GapStatus.MISSING
    assert _gap_row("Art. 50", tmp_path).status == GapStatus.MISSING


def test_art49_registration_artifact_is_partial_never_met(tmp_path):
    assert _row("Art. 49", tmp_path).status == GapStatus.MISSING
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "eu-database-registration.md").write_text(
        "# reg\n", encoding="utf-8"
    )
    for row in (_row("Art. 49", tmp_path), _gap_row("Art. 49", tmp_path)):
        assert row.status == GapStatus.PARTIAL
        assert row.status != GapStatus.MET


def test_art26_without_records_is_missing(tmp_path):
    assert _row("Art. 26", tmp_path).status == GapStatus.MISSING
    assert _gap_row("Art. 26", tmp_path).status == GapStatus.MISSING


def test_art26_deployer_use_records_is_partial_never_met(tmp_path):
    (tmp_path / "DEPLOYER_USE_RECORDS.md").write_text("# use\n", encoding="utf-8")
    for row in (_row("Art. 26", tmp_path), _gap_row("Art. 26", tmp_path)):
        assert row.status == GapStatus.PARTIAL
        assert row.status != GapStatus.MET


def test_no_repo_root_stays_unverified():
    for article in ARTICLES:
        assert _row(article, None).status == GapStatus.UNVERIFIED


def test_new_probe_refs_carry_provenance():
    for article in ARTICLES:
        entry = PROBE_PROVENANCE[_ref(article)]
        assert entry["source"]
        assert entry["confidence"] in {"low", "medium"}
        assert entry["needs_founder_review"] is True


def test_risk_register_wording_unchanged(tmp_path):
    (tmp_path / "risk_register.json").write_text("{}", encoding="utf-8")
    row = artifact_gap_status("risk_register", tmp_path)
    assert "lacks risk-identification and mitigation content markers" in row.rationale
    assert "a bare or empty file is not a risk register." in row.rationale
    assert row.confidence == 0.35
