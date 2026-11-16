"""Pack-local probes of DORA: the register of information and the incident report."""

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
    / "DORA"
    / "probes.json"
)
PREFIX = "dora"
REGISTER = "dora.register_of_information"
INCIDENT = "dora.incident_report"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."

CLAUSE_IDS = (
    "classification",
    "initial-notification",
    "intermediate-report",
    "final-report",
    "client-information",
)

REGISTER_TEXT = (
    "Provider: Example Cloud Ltd supplies hosting.\n"
    "Function supported: payment processing service.\n"
    "Critical or important: yes, the function is critical.\n"
)

REALISTIC = {
    "classification": "We classify each incident against the severity criteria and the threshold set by the risk team.",
    "initial-notification": "The initial notification goes to the competent authority within the hours set in our runbook.",
    "intermediate-report": "An intermediate report gives a status update and the recovery steps taken since the last note.",
    "final-report": "The final report records the root cause, the fixes made and the lessons the team agreed on.",
    "client-information": "Affected clients are informed by the service desk, and we communicate the steps they should take.",
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _document(bodies: dict[str, str]) -> str:
    return "\n".join(f"<!-- clause: {c} -->\n{t}\n" for c, t in bodies.items())


def test_the_file_parses_with_the_pack_prefix():
    parsed = parse_probe_file(PROBE_FILE, prefix=PREFIX)
    assert set(parsed) == {REGISTER, INCIDENT}


def test_provenance_follows_the_heuristic_rule():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    assert data["family"] == "dora"
    assert tuple(data["probes"][INCIDENT]["clauses"]) == CLAUSE_IDS
    for probe in data["probes"].values():
        prov = probe["provenance"]
        assert prov["source"].startswith("heuristic (no legal source):")
        assert prov["confidence"] == "low"
        assert prov["needs_founder_review"] is True


def test_globs_have_twins_and_none_is_bare():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    for probe in data["probes"].values():
        patterns = probe["patterns"]
        assert "**/*.md" not in patterns
        for pat in patterns:
            if "-" in pat:
                assert pat.replace("-", "_") in patterns


def test_the_refs_exist():
    assert probe_exists(REGISTER)
    assert probe_exists(INCIDENT)
    for clause in CLAUSE_IDS:
        assert probe_exists(f"{INCIDENT}#{clause}")
    assert not probe_exists(f"{INCIDENT}#nothing")


def test_realistic_text_covers_every_clause():
    assert tuple(REALISTIC) == CLAUSE_IDS


def test_register_empty_repo_is_missing(tmp_path: Path):
    assert artifact_gap_status(REGISTER, tmp_path).status == GapStatus.MISSING


def test_register_unrelated_sentence_is_partial_035(tmp_path: Path):
    _write(tmp_path, "docs/register-of-information.md", UNRELATED)
    row = artifact_gap_status(REGISTER, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


def test_register_realistic_file_is_partial_06(tmp_path: Path):
    _write(tmp_path, "docs/register-of-information.md", REGISTER_TEXT)
    row = artifact_gap_status(REGISTER, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize(
    "rel",
    [
        "register-of-information.md",
        "docs/register_of_information.md",
        "docs/ict-provider-register.md",
        "docs/ict_provider_register.md",
        "docs/vendors/ict-third-party-list.md",
        "docs/ict_third_party_list.md",
    ],
)
def test_register_every_glob_spelling_finds_the_file(tmp_path: Path, rel: str):
    _write(tmp_path, rel, REGISTER_TEXT)
    row = artifact_gap_status(REGISTER, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_an_ordinary_markdown_file_is_not_evidence(tmp_path: Path):
    _write(tmp_path, "README.md", REGISTER_TEXT + _document(REALISTIC))
    assert artifact_gap_status(REGISTER, tmp_path).status == GapStatus.MISSING
    row = artifact_gap_status(f"{INCIDENT}#final-report", tmp_path)
    assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_incident_empty_repo_is_missing(tmp_path: Path, clause: str):
    row = artifact_gap_status(f"{INCIDENT}#{clause}", tmp_path)
    assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_incident_unrelated_sentence_is_partial_035(tmp_path: Path, clause: str):
    _write(tmp_path, "docs/major-incident-report.md", _document({clause: UNRELATED}))
    row = artifact_gap_status(f"{INCIDENT}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_incident_realistic_section_is_partial_06(tmp_path: Path, clause: str):
    _write(
        tmp_path,
        "docs/major-incident-report.md",
        _document({clause: REALISTIC[clause]}),
    )
    row = artifact_gap_status(f"{INCIDENT}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize(
    "rel",
    [
        "major-incident-report.md",
        "docs/major_incident_report_2026.md",
        "docs/ict-incident-report.md",
        "docs/ict_incident_report.md",
    ],
)
def test_incident_every_glob_spelling_finds_the_file(tmp_path: Path, rel: str):
    _write(tmp_path, rel, _document({"final-report": REALISTIC["final-report"]}))
    row = artifact_gap_status(f"{INCIDENT}#final-report", tmp_path)
    assert row.confidence == pytest.approx(0.6)


def test_a_full_incident_document_is_partial_never_met(tmp_path: Path):
    _write(tmp_path, "docs/major-incident-report.md", _document(REALISTIC))
    row = artifact_gap_status(INCIDENT, tmp_path)
    assert row.status == GapStatus.PARTIAL
