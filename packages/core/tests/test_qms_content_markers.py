"""Per-clause QMS content markers (SU-23b): scaffold text is never "Present"."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.gap_probes import (
    _CONTENT_MARKERS,
    _PROBE_PATTERNS,
    QMS_17_1_CLAUSES,
    SCAFFOLD_PLACEHOLDER,
    artifact_gap_status,
    qms_clause_results,
)
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import GapStatus
from opencomplai_core.qms_document import build_qms_document

_FILLED = (
    "This procedure documents regulatory compliance, design control, quality "
    "assurance, testing validation, technical specifications and standards, "
    "data governance, risk management, post-market monitoring, incident "
    "reporting, authority communication, record retention, resource planning "
    "and accountability.\n"
)

# One keyword per clause, written independently of the production table.
_KEYWORD = {
    "a": "compliance",
    "b": "design",
    "c": "quality assurance",
    "d": "validation",
    "e": "standards",
    "f": "data governance",
    "g": "risk",
    "h": "post-market",
    "i": "incident",
    "j": "authority",
    "k": "records",
    "l": "resources",
    "m": "accountability",
}


def _root_file(ref: str) -> str:
    """The plain root-level filename among a clause's probe patterns."""
    return next(p for p in _PROBE_PATTERNS[ref] if "*" not in p and "/" not in p)


def _write(tmp_path: Path, letter: str, text: str) -> None:
    ref = f"provider_qms_17_1_{letter}"
    (tmp_path / _root_file(ref)).write_text(text, encoding="utf-8")


def _label(tmp_path: Path, letter: str = "b") -> str:
    return next(r for r in qms_clause_results(tmp_path) if r.letter == letter).label


def test_scaffold_only_file_is_unfilled(tmp_path: Path):
    _write(
        tmp_path,
        "b",
        "# Design control\n\nThe design of the system is described in this "
        f"section for every release. Owner: {SCAFFOLD_PLACEHOLDER}\n",
    )
    assert _label(tmp_path) == "Unfilled"
    row = artifact_gap_status("provider_qms_17_1_b", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35
    assert "1 unfilled scaffold placeholder(s) ('_fill in_')" in row.rationale


def test_heading_only_file_is_unfilled(tmp_path: Path):
    _write(tmp_path, "b", "# Design control\n\n## Design reviews\n\n### Design\n")
    assert _label(tmp_path) == "Unfilled"
    _write(tmp_path, "b", "")
    assert _label(tmp_path) == "Unfilled"
    _write(tmp_path, "b", "Design control exists.\n")  # under 8 body words
    assert _label(tmp_path) == "Unfilled"


def test_filled_file_is_present(tmp_path: Path):
    _write(tmp_path, "b", _FILLED)
    assert _label(tmp_path) == "Present"
    row = artifact_gap_status("provider_qms_17_1_b", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.6


def test_every_clause_has_a_marker_spec_and_accepts_its_own_keyword(tmp_path: Path):
    for letter, ref, _title in QMS_17_1_CLAUSES:
        assert ref in _CONTENT_MARKERS, f"missing marker spec for {ref}"
        _write(
            tmp_path,
            letter,
            f"# Heading\n\nThis document describes our {_KEYWORD[letter]} "
            "approach in enough words to count as body text.\n",
        )
    labels = {r.letter: r.label for r in qms_clause_results(tmp_path)}
    assert labels == dict.fromkeys("abcdefghijklm", "Present")


def test_keyword_free_body_is_unfilled_for_every_clause(tmp_path: Path):
    for letter, _ref, _title in QMS_17_1_CLAUSES:
        _write(
            tmp_path,
            letter,
            "Lorem ipsum dolor sit amet consectetur adipiscing elit.\n",
        )
    labels = {r.letter: r.label for r in qms_clause_results(tmp_path)}
    assert labels == dict.fromkeys("abcdefghijklm", "Unfilled")


def test_partially_filled_file_stays_unfilled(tmp_path: Path):
    _write(tmp_path, "b", _FILLED + f"Reviewer: {SCAFFOLD_PLACEHOLDER}\n")
    assert _label(tmp_path) == "Unfilled"


def test_fully_filled_qms_art17_is_partial_never_met(tmp_path: Path):
    for letter, _ref, _title in QMS_17_1_CLAUSES:
        _write(tmp_path, letter, _FILLED)
    results = qms_clause_results(tmp_path)
    assert all(r.row.status != GapStatus.MET for r in results)
    assert all(r.label == "Present" for r in results)

    load_gap_article_map.cache_clear()
    report = build_gap_report("sys", "HEAD", repo_root=tmp_path)
    art17 = next(r for r in report.articles if r.article == "Art. 17")
    assert art17.status == GapStatus.PARTIAL
    assert "Per-clause: 13 present / 0 unfilled / 0 missing (of 13)." in art17.rationale


def test_whole_article_missing_escalates_to_partial_when_clause_file_exists(
    tmp_path: Path,
):
    _write(tmp_path, "b", _FILLED)
    row = artifact_gap_status("provider_qms", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.evidence_ref == _root_file("provider_qms_17_1_b")
    assert row.confidence == 0.4
    assert "Per-clause: 1 present / 0 unfilled / 12 missing (of 13)." in row.rationale


def test_whole_article_unchanged_when_no_clause_file(tmp_path: Path):
    row = artifact_gap_status("provider_qms", tmp_path)
    assert row.status == GapStatus.MISSING
    assert "Per-clause" not in row.rationale
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "qms.md").write_text("Our quality management system.", encoding="utf-8")
    row = artifact_gap_status("provider_qms", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert "Per-clause" not in row.rationale


def test_risk_register_rationale_strings_unchanged(tmp_path: Path):
    (tmp_path / "risk_register.json").write_text("{}", encoding="utf-8")
    row = artifact_gap_status("risk_register", tmp_path)
    assert row.rationale == (
        "Found 'risk_register.json' but it lacks risk-identification and mitigation "
        "content markers — a bare or empty file is not a risk register."
    )
    (tmp_path / "risk_register.json").write_text(
        "risk identification and mitigation", encoding="utf-8"
    )
    row = artifact_gap_status("risk_register", tmp_path)
    assert (
        "with content markers found (risk identification + mitigation). "
        in row.rationale
    )


def test_clause_entry_carries_confidence(tmp_path: Path):
    _write(tmp_path, "b", _FILLED)
    _write(tmp_path, "c", "# Only a heading\n")
    by_letter = {c.letter: c for c in build_qms_document(tmp_path).clauses}
    assert by_letter["b"].confidence == 0.6
    assert by_letter["c"].confidence == 0.35
    assert by_letter["c"].status_label == "Unfilled"
    assert by_letter["a"].confidence == 0.4
    assert all(c.confidence is None for c in build_qms_document(None).clauses)
