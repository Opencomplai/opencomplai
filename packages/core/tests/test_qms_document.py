"""Tests for the Art. 17(1)(a)-(m) QMS document builder (CP-15).

Fixture mirrors `test_qms_article_17_clauses.py`'s exact 6/13 present split
(clauses a-f present, g-m missing) -- CP-15's own Accept criterion asks for
the identical split "for consistency" with CP-7.
"""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.gap_probes import QMS_17_1_CLAUSES
from opencomplai_core.models import GapStatus
from opencomplai_core.qms_document import (
    build_qms_document,
    render_qms_document_markdown,
)

_PRESENT_CLAUSE_FILES = {
    "a": "REGULATORY_COMPLIANCE_STRATEGY.md",
    "b": "DESIGN_CONTROL.md",
    "c": "QUALITY_MANAGEMENT_PROCEDURES.md",
    "d": "TESTING_VALIDATION.md",
    "e": "TECHNICAL_DOCUMENTATION.md",
    "f": "DATA_GOVERNANCE.md",
}
# (g)-(m) intentionally left without any matching evidence file.


def test_document_without_repo_root_is_thirteen_unverified_rows():
    doc = build_qms_document(None)
    assert len(doc.clauses) == 13
    assert doc.present_count == 0
    assert doc.missing_count == 0
    assert doc.unverified_count == 13
    assert all(c.status == GapStatus.UNVERIFIED for c in doc.clauses)
    assert all(c.status_label == "Unverified" for c in doc.clauses)


def test_six_of_thirteen_present_not_one_article_verdict(tmp_path: Path):
    for filename in _PRESENT_CLAUSE_FILES.values():
        (tmp_path / filename).write_text("evidence\n", encoding="utf-8")

    doc = build_qms_document(tmp_path, system_id="qms-fixture", commit_ref="abc123")
    assert len(doc.clauses) == 13

    by_letter = {c.letter: c for c in doc.clauses}
    for letter in _PRESENT_CLAUSE_FILES:
        assert by_letter[letter].status_label == "Present", letter
    for letter in "ghijklm":
        assert by_letter[letter].status_label == "Missing", letter

    assert (doc.present_count, doc.missing_count, doc.unverified_count) == (6, 7, 0)
    # Letters stay in Art. 17(1) order, matching QMS_17_1_CLAUSES.
    assert [c.letter for c in doc.clauses] == [
        letter for letter, _, _ in QMS_17_1_CLAUSES
    ]


def test_markdown_document_shows_per_clause_status_not_single_verdict(
    tmp_path: Path,
):
    for filename in _PRESENT_CLAUSE_FILES.values():
        (tmp_path / filename).write_text("evidence\n", encoding="utf-8")

    doc = build_qms_document(tmp_path, system_id="qms-fixture")
    rendered = render_qms_document_markdown(doc)

    assert "Art. 17(1)(a)-(m)" in rendered
    assert rendered.count("| Present |") == 6
    assert rendered.count("| Missing |") == 7
    assert "6 present / 7 missing" in rendered
    assert "qms-fixture" in rendered
    # Every one of the 13 clause titles appears -- a per-clause breakdown,
    # never a single whole-article status.
    for _letter, _ref, title in QMS_17_1_CLAUSES:
        assert title in rendered


def test_evidence_hashes_cited_when_supplied(tmp_path: Path):
    doc = build_qms_document(tmp_path, evidence_hashes=["sha256:deadbeef"])
    rendered = render_qms_document_markdown(doc)
    assert "sha256:deadbeef" in rendered


def test_no_evidence_hashes_stays_honest_not_fabricated(tmp_path: Path):
    doc = build_qms_document(tmp_path)
    rendered = render_qms_document_markdown(doc)
    assert "No evidence-vault references supplied" in rendered
