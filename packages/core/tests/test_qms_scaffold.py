"""Tests for `scaffold_qms` (SU-24a1): starter Art. 17(1)(a)-(m) clause files."""

from __future__ import annotations

import hashlib
from pathlib import Path

from opencomplai_core.gap_probes import (
    QMS_17_1_CLAUSES,
    SCAFFOLD_PLACEHOLDER,
    qms_clause_results,
    run_artifact_probe,
)
from opencomplai_core.qms_document import (
    _SCAFFOLD_TEMPLATE,
    QMS_SCAFFOLD_STEMS,
    scaffold_qms,
)


def _files(root: Path) -> list[Path]:
    return [root / "docs" / "qms" / f"{s}.md" for s in QMS_SCAFFOLD_STEMS.values()]


def _hashes(root: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in _files(root)}


def test_scaffold_writes_thirteen_files_all_unfilled(tmp_path: Path) -> None:
    entries = scaffold_qms(tmp_path)
    assert [e.action for e in entries] == ["created"] * 13
    results = qms_clause_results(tmp_path)
    assert [r.label for r in results] == ["Unfilled"] * 13
    assert all(r.content_bearing is not True for r in results)
    for p in _files(tmp_path):
        assert SCAFFOLD_PLACEHOLDER in p.read_text(encoding="utf-8")


def test_second_run_changes_nothing(tmp_path: Path) -> None:
    scaffold_qms(tmp_path)
    before = _hashes(tmp_path)
    entries = scaffold_qms(tmp_path)
    assert [e.action for e in entries] == ["skipped"] * 13
    assert _hashes(tmp_path) == before


def test_existing_file_is_never_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "qms" / "design-control.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"my own design control text\n")
    entries = scaffold_qms(tmp_path)
    assert target.read_bytes() == b"my own design control text\n"
    by_letter = {e.letter: e.action for e in entries}
    assert by_letter["b"] == "skipped"
    assert sum(a == "created" for a in by_letter.values()) == 12


def test_user_file_elsewhere_blocks_scaffold_for_that_clause(tmp_path: Path) -> None:
    (tmp_path / "DESIGN_CONTROL.md").write_text("our design control\n")
    entries = scaffold_qms(tmp_path)
    assert not (tmp_path / "docs" / "qms" / "design-control.md").exists()
    assert {e.letter: e.action for e in entries}["b"] == "skipped"


def test_edited_scaffold_file_reads_present(tmp_path: Path) -> None:
    scaffold_qms(tmp_path)
    (tmp_path / "docs" / "qms" / "risk-management-system.md").write_text(
        "We identify and assess every risk to health, safety and fundamental "
        "rights, record it in the register, and review it each quarter.\n",
        encoding="utf-8",
    )
    labels = {r.letter: r.label for r in qms_clause_results(tmp_path)}
    assert labels.pop("g") == "Present"
    assert set(labels.values()) == {"Unfilled"}


def test_scaffold_stems_match_clause_probes(tmp_path: Path) -> None:
    scaffold_qms(tmp_path)
    for letter, ref, _title in QMS_17_1_CLAUSES:
        rel = f"docs/qms/{QMS_SCAFFOLD_STEMS[letter]}.md"
        assert rel in run_artifact_probe(ref, tmp_path).found_paths, letter


def test_template_carries_review_flag() -> None:
    first = _SCAFFOLD_TEMPLATE.read_text(encoding="utf-8").splitlines()[0]
    assert "needs_founder_review=true" in first
