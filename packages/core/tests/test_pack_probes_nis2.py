"""Pack-local probes of NIS2: one incident notification record read stage by stage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.gap_probes import artifact_gap_status, probe_exists
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import parse_probe_file

PROBE_FILE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "opencomplai_core"
    / "packs"
    / "NIS2"
    / "probes.json"
)
PREFIX = "nis2"
REF = "nis2.incident_notification_record"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."
CLAUSE_IDS = ("early-warning", "notification", "intermediate-report", "final-report")

REALISTIC = {
    "early-warning": "Early warning sent to the national authority on 2026-03-04 at 09:30, within the first day of awareness.",
    "notification": "Incident notification submitted on 2026-03-05 at 14:00 with severity, impact and the suspected cause.",
    "intermediate-report": "Intermediate report sent on 2026-03-12 after the authority asked for a status update on containment.",
    "final-report": "Final report filed on 2026-04-02 with the root cause, mitigation applied and cross-border impact.",
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _document(bodies: dict[str, str]) -> str:
    return "\n".join(f"<!-- clause: {c} -->\n{t}\n" for c, t in bodies.items())


def test_the_file_parses_with_the_pack_prefix():
    parsed = parse_probe_file(PROBE_FILE, prefix=PREFIX)
    assert tuple(parsed) == (REF,)


def test_the_file_declares_the_family_and_every_clause():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    assert data["family"] == "nis2"
    probe = data["probes"][REF]
    assert probe["type"] == "clause_document"
    assert probe["noun"] == "incident notification record"
    assert tuple(probe["clauses"]) == CLAUSE_IDS
    prov = probe["provenance"]
    assert prov["source"].startswith("heuristic (no legal source):")
    assert prov["confidence"] == "low"
    assert prov["needs_founder_review"] is True


def test_every_glob_has_its_underscore_twin_and_none_is_bare():
    patterns = json.loads(PROBE_FILE.read_text(encoding="utf-8"))["probes"][REF][
        "patterns"
    ]
    assert "**/*.md" not in patterns
    for pat in patterns:
        if "-" in pat:
            assert pat.replace("-", "_") in patterns


def test_the_pack_lists_the_probe_file():
    pack = PROBE_FILE.with_name("pack.json")
    assert "probes.json" in json.loads(pack.read_text(encoding="utf-8"))["data_files"]


def test_the_ref_and_every_clause_ref_exist():
    assert probe_exists(REF)
    for clause in CLAUSE_IDS:
        assert probe_exists(f"{REF}#{clause}")
    assert not probe_exists(f"{REF}#no_such_stage")


def test_realistic_text_covers_every_clause():
    assert tuple(REALISTIC) == CLAUSE_IDS


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_an_empty_repo_is_missing(tmp_path: Path, clause: str):
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.MISSING


def test_an_empty_repo_is_not_met_for_the_whole_document(tmp_path: Path):
    assert artifact_gap_status(REF, tmp_path).status != GapStatus.MET


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_section_with_one_unrelated_sentence_is_partial_035(
    tmp_path: Path, clause: str
):
    _write(tmp_path, "incident-notification.md", _document({clause: UNRELATED}))
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_file_without_the_clause_anchor_is_partial_035(tmp_path: Path, clause: str):
    _write(tmp_path, "incident-notification.md", UNRELATED)
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_short_realistic_section_is_partial_06_never_met(tmp_path: Path, clause: str):
    _write(
        tmp_path,
        "incident-notification.md",
        _document({clause: REALISTIC[clause]}),
    )
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_a_full_document_is_partial_never_met(tmp_path: Path):
    _write(tmp_path, "incident-notification.md", _document(REALISTIC))
    assert artifact_gap_status(REF, tmp_path).status == GapStatus.PARTIAL


@pytest.mark.parametrize(
    "rel",
    [
        "incident-notification.md",
        "incident_notification.md",
        "docs/incident-notification-2026.md",
        "docs/nis2/nis2-notification.md",
        "docs/nis2_notification.md",
        "x/incident_notification.md",
    ],
)
def test_every_glob_spelling_finds_the_file(tmp_path: Path, rel: str):
    _write(tmp_path, rel, _document({"final-report": REALISTIC["final-report"]}))
    row = artifact_gap_status(f"{REF}#final-report", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_an_ordinary_markdown_file_is_not_evidence(tmp_path: Path):
    _write(tmp_path, "README.md", _document(REALISTIC))
    row = artifact_gap_status(f"{REF}#final-report", tmp_path)
    assert row.status == GapStatus.MISSING
