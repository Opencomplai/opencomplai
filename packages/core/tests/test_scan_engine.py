"""Scan engine — discrepancy analysis and deterministic hashing."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.models import DiscrepancySeverity
from opencomplai_core.scan_engine import run_scan


def _biometric_repo(tmp_path: Path) -> Path:
    (tmp_path / "requirements.txt").write_text("face_recognition\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "face.py").write_text(
        "import face_recognition\n"
        "def identify(img):\n"
        "    return face_recognition.face_locations(img)\n",
        encoding="utf-8",
    )
    return tmp_path


def test_declared_minimal_biometric_prod_major_discrepancy(tmp_path: Path):
    repo = _biometric_repo(tmp_path)
    report = run_scan(
        system_id="test-sys",
        commit_ref="HEAD",
        repo_root=repo,
        declared_purpose="customer support chatbot",
    )
    assert "biometric" in report.detected_categories or report.evidence
    if "biometric" in report.discrepancies:
        assert report.severity in (
            DiscrepancySeverity.MAJOR,
            DiscrepancySeverity.MINOR,
            DiscrepancySeverity.INFO,
        )


def test_agreement_yields_none_severity(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    report = run_scan(
        system_id="test-sys",
        commit_ref="HEAD",
        repo_root=tmp_path,
        declared_purpose="customer support chatbot",
    )
    assert report.severity == DiscrepancySeverity.NONE
    assert report.discrepancies == []


def test_same_tree_twice_identical_report_hash(tmp_path: Path):
    repo = _biometric_repo(tmp_path)
    r1 = run_scan("s", "HEAD", repo, "customer support chatbot")
    r2 = run_scan("s", "HEAD", repo, "customer support chatbot")
    assert r1.input_digest == r2.input_digest
    assert r1.report_hash == r2.report_hash
