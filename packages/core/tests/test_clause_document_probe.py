"""Clause-document probes: one document, N clauses, `<ref>#<clause>` rows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core import gap_probes
from opencomplai_core.gap_probes import (
    _CLAUSE_DOCUMENTS,
    _CODE_HINTS,
    _CONTENT_MARKERS,
    _PROBE_PATTERNS,
    PROBE_PROVENANCE,
    SCAFFOLD_PLACEHOLDER,
    _register_probe_files,
    artifact_gap_status,
    clause_document_results,
    probe_exists,
    qms_clause_results,
    registry_snapshot,
    run_artifact_probe,
    supporting_gap_status,
)
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import parse_probe_file

REF = "unit_clause_doc"
DOC = "docs/unit_clause_doc.md"

PROBE = {
    "family": "unit_clause",
    "probes": {
        REF: {
            "type": "clause_document",
            "patterns": ["docs/unit_clause_doc*.md"],
            "noun": "unit policy",
            "provenance": {
                "source": "heuristic (no legal source): unit test",
                "confidence": "low",
            },
            "clauses": {
                "4.1": {
                    "title": "Scope",
                    "markers": [{"re": "scope", "flags": "i"}],
                },
                "4.2 (a)": {
                    "title": "Roles",
                    "markers": [
                        {"re": "owner", "flags": "i"},
                        {"re": "review", "flags": "i"},
                    ],
                },
                "5": {"title": "Records", "markers": [{"re": "retain", "flags": "i"}]},
                "6": {"title": "Audit", "markers": [{"re": "audit", "flags": "i"}]},
            },
        }
    },
}

_WORDS = "this section describes how the team handles the matter in practice and keeps it current"


@pytest.fixture
def tables():
    tabs = (
        _PROBE_PATTERNS,
        _CONTENT_MARKERS,
        _CODE_HINTS,
        PROBE_PROVENANCE,
        _CLAUSE_DOCUMENTS,
    )
    saved = [(t, dict(t)) for t in tabs]
    yield
    for table, copy in saved:
        table.clear()
        table.update(copy)


@pytest.fixture
def registered(tmp_path: Path, tables) -> Path:
    path = tmp_path / "probes" / "unit_clause.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(PROBE), encoding="utf-8")
    _register_probe_files([(path, None)])
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    return repo


def _doc(repo: Path, text: str) -> None:
    (repo / DOC).write_text(text, encoding="utf-8")


FULL = (
    f"# Policy\n<!-- clause: 4.1 -->\nThe scope covers {_WORDS}.\n"
    f"<!-- clause: 4.2 (a) -->\nThe owner runs a review because {_WORDS}.\n"
    f"<!-- clause: 5 -->\nWe retain records. {SCAFFOLD_PLACEHOLDER}\n"
    f"<!-- clause: 6 -->\nshort audit\n"
)


def test_no_repo_root_is_unverified(registered: Path):
    row = artifact_gap_status(f"{REF}#4.1", None)
    assert row.status == GapStatus.UNVERIFIED
    assert row.confidence is None
    assert artifact_gap_status(REF, None).status == GapStatus.UNVERIFIED


def test_no_file_is_missing(registered: Path):
    row = artifact_gap_status(f"{REF}#4.1", registered)
    assert (row.status, row.confidence) == (GapStatus.MISSING, 0.4)
    assert artifact_gap_status(REF, registered).status == GapStatus.MISSING


def test_present_clause_is_partial_06(registered: Path):
    _doc(registered, FULL)
    row = artifact_gap_status(f"{REF}#4.1", registered)
    assert (row.status, row.confidence) == (GapStatus.PARTIAL, 0.6)
    assert row.evidence_ref == DOC
    assert "'4.1'" in row.rationale
    assert DOC in row.rationale
    spaced = artifact_gap_status(f"{REF}#4.2 (a)", registered)
    assert (spaced.status, spaced.confidence) == (GapStatus.PARTIAL, 0.6)


def test_unfilled_clause_is_partial_035(registered: Path):
    _doc(registered, FULL)
    for clause in ("5", "6"):  # placeholder; too few words
        row = artifact_gap_status(f"{REF}#{clause}", registered)
        assert (row.status, row.confidence) == (GapStatus.PARTIAL, 0.35)
        assert DOC in row.rationale
        assert f"'{clause}'" in row.rationale
    # enough words, marker absent
    _doc(registered, f"<!-- clause: 4.1 -->\nNothing relevant: {_WORDS}.\n")
    row = artifact_gap_status(f"{REF}#4.1", registered)
    assert (row.status, row.confidence) == (GapStatus.PARTIAL, 0.35)


def test_missing_anchor_in_existing_document_is_partial_035(registered: Path):
    _doc(registered, "<!-- clause: 4.1 -->\nThe scope covers " + _WORDS + ".\n")
    row = artifact_gap_status(f"{REF}#6", registered)
    assert (row.status, row.confidence) == (GapStatus.PARTIAL, 0.35)
    assert DOC in row.rationale
    assert "'6'" in row.rationale


def test_a_clause_is_never_met(registered: Path):
    _doc(registered, FULL)
    for result in clause_document_results(REF, registered):
        assert result.row.status != GapStatus.MET


def test_clause_results_states_and_order(registered: Path):
    _doc(registered, FULL)
    results = clause_document_results(REF, registered)
    assert [(r.clause, r.title, r.state) for r in results] == [
        ("4.1", "Scope", "present"),
        ("4.2 (a)", "Roles", "present"),
        ("5", "Records", "unfilled"),
        ("6", "Audit", "unfilled"),
    ]
    assert {r.state for r in clause_document_results(REF, None)} == {"unverified"}


def test_bare_ref_fold(registered: Path):
    _doc(registered, FULL)
    row = artifact_gap_status(REF, registered)
    assert (row.status, row.confidence) == (GapStatus.PARTIAL, 0.6)
    assert row.evidence_ref == DOC
    assert row.rationale.endswith(
        "Per-clause: 2 present / 2 unfilled / 0 missing (of 4)."
    )

    _doc(registered, "<!-- clause: 4.1 -->\nshort\n")
    row = artifact_gap_status(REF, registered)
    assert (row.status, row.confidence) == (GapStatus.PARTIAL, 0.35)
    assert row.rationale.endswith(
        "Per-clause: 0 present / 1 unfilled / 3 missing (of 4)."
    )


def test_first_sorted_match_is_the_document(registered: Path):
    _doc(registered, "<!-- clause: 4.1 -->\nshort\n")
    (registered / "docs" / "unit_clause_doc_a.md").write_text(FULL, encoding="utf-8")
    row = artifact_gap_status(REF, registered)
    assert row.evidence_ref == "docs/unit_clause_doc.md"


def test_unknown_clause_and_plain_probe_raise(registered: Path):
    with pytest.raises(ValueError, match="no clause"):
        artifact_gap_status(f"{REF}#nope", registered)
    with pytest.raises(ValueError, match="no clause"):
        run_artifact_probe(f"{REF}#nope", registered)
    with pytest.raises(ValueError, match="no clause"):
        supporting_gap_status(f"{REF}#nope", registered)
    plain = next(r for r in _PROBE_PATTERNS if r not in _CLAUSE_DOCUMENTS)
    with pytest.raises(ValueError, match="not a clause document"):
        artifact_gap_status(f"{plain}#x", registered)
    with pytest.raises(ValueError, match="not a clause document"):
        artifact_gap_status(f"{plain}#x", None)


def test_content_markers_met_only_for_a_present_clause(registered: Path):
    _doc(registered, FULL)
    assert run_artifact_probe(f"{REF}#4.1", registered).content_markers_met is True
    unfilled = run_artifact_probe(f"{REF}#5", registered)
    assert unfilled.content_markers_met is False
    assert unfilled.scaffold_hits == 1
    assert run_artifact_probe(REF, registered).content_markers_met is None
    assert run_artifact_probe(f"{REF}#4.1", None).found_paths == []


def test_supporting_status_only_for_evidence(registered: Path):
    assert supporting_gap_status(f"{REF}#4.1", registered) is None
    assert supporting_gap_status(REF, registered) is None
    _doc(registered, FULL)
    assert supporting_gap_status(f"{REF}#4.1", registered) is not None
    assert supporting_gap_status(f"{REF}#5", registered) is None
    assert supporting_gap_status(REF, registered) is not None


def test_probe_exists(registered: Path):
    assert probe_exists(REF)
    assert probe_exists(f"{REF}#4.1")
    assert not probe_exists(f"{REF}#nope")
    assert not probe_exists("no_such_probe")
    plain = next(r for r in _PROBE_PATTERNS if r not in _CLAUSE_DOCUMENTS)
    assert probe_exists(plain)
    assert not probe_exists(f"{plain}#x")


def test_snapshot_lists_the_clause_document(registered: Path):
    entry = registry_snapshot()[REF]
    assert entry["type"] == "clause_document"
    assert entry["noun"] == "unit policy"
    assert entry["markers"] is None
    assert entry["clauses"]["4.2 (a)"] == {
        "title": "Roles",
        "markers": [["owner", "i"], ["review", "i"]],
    }
    assert "type" not in next(v for k, v in registry_snapshot().items() if k != REF)


def test_duplicate_clause_document_ref_raises(registered: Path, tmp_path: Path):
    again = tmp_path / "again.json"
    again.write_text(json.dumps(PROBE), encoding="utf-8")
    with pytest.raises(ValueError, match="already registered"):
        _register_probe_files([(again, None)])


def _bad(tmp_path: Path, mutate) -> Path:
    data = json.loads(json.dumps(PROBE))
    mutate(data["probes"][REF])
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(clauses={}),
        lambda p: p["clauses"]["4.1"].update(markers=[]),
        lambda p: p["clauses"].update({"-bad": p["clauses"].pop("4.1")}),
        lambda p: p["clauses"].update({"a#b": p["clauses"].pop("4.1")}),
        lambda p: p.update(markers={"all": []}),
        lambda p: p.update(code_hint={"re": "x", "flags": ""}),
        lambda p: p.update(type="other"),
        lambda p: p.pop("noun"),
        lambda p: p.pop("provenance"),
        lambda p: p["clauses"]["4.1"].pop("title"),
        lambda p: p["clauses"]["4.1"]["markers"][0].update(re="("),
    ],
)
def test_clause_document_format_faults(tmp_path: Path, mutate):
    with pytest.raises(ValueError, match=REF):
        parse_probe_file(_bad(tmp_path, mutate))


def test_qms_clause_results_unchanged(tmp_path: Path):
    results = qms_clause_results(tmp_path)
    assert [r.letter for r in results] == list("abcdefghijklm")
    assert {r.row.status for r in results} == {GapStatus.MISSING}
    assert qms_clause_results(None)[0].row.status == GapStatus.UNVERIFIED
    assert gap_probes.QMS_17_1_CLAUSES[0][0] == "a"
    assert "provider_qms" not in _CLAUSE_DOCUMENTS
