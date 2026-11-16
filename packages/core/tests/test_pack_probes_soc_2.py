"""Pack-local probes of SOC 2: the system description and the control matrix."""

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
    / "SOC_2"
    / "probes.json"
)
PREFIX = "soc_2"
DESCRIPTION = "soc_2.system_description"
MATRIX = "soc_2.control_matrix"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."

CLAUSE_IDS = ("services", "components", "boundaries", "commitments", "incidents")

REALISTIC = {
    "services": "The service gives customers a hosted reporting tool.",
    "components": "Components: the application software, the hosting infrastructure and the data stores.",
    "boundaries": "The boundary is the production platform; the office network is out of scope.",
    "commitments": "Our commitments to customers are set in the agreement, with an availability objective.",
    "incidents": "No incidents in the period; the response procedure is unchanged.",
}

MATRIX_TEXT = (
    "| Criterion | Control | Evidence |\n"
    "| CC6.1 | We restrict production access to named staff | access review ticket |\n"
)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _document(bodies: dict[str, str]) -> str:
    return "\n".join(f"<!-- clause: {c} -->\n{t}\n" for c, t in bodies.items())


def test_the_file_parses_with_the_pack_prefix():
    parsed = parse_probe_file(PROBE_FILE, prefix=PREFIX)
    assert set(parsed) == {DESCRIPTION, MATRIX}


def test_provenance_follows_the_heuristic_rule():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    assert data["family"] == "soc_2"
    assert tuple(data["probes"][DESCRIPTION]["clauses"]) == CLAUSE_IDS
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
    assert probe_exists(DESCRIPTION)
    assert probe_exists(MATRIX)
    for clause in CLAUSE_IDS:
        assert probe_exists(f"{DESCRIPTION}#{clause}")
    assert not probe_exists(f"{DESCRIPTION}#nothing")


def test_realistic_text_covers_every_clause():
    assert tuple(REALISTIC) == CLAUSE_IDS


def test_matrix_empty_repo_is_missing(tmp_path: Path):
    assert artifact_gap_status(MATRIX, tmp_path).status == GapStatus.MISSING


def test_matrix_unrelated_sentence_is_partial_035(tmp_path: Path):
    _write(tmp_path, "docs/control-matrix.md", UNRELATED)
    row = artifact_gap_status(MATRIX, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


def test_matrix_realistic_file_is_partial_06(tmp_path: Path):
    _write(tmp_path, "docs/control-matrix.md", MATRIX_TEXT)
    row = artifact_gap_status(MATRIX, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize(
    "rel",
    [
        "control-matrix.md",
        "docs/control_matrix.md",
        "docs/assurance/soc-controls.md",
    ],
)
def test_matrix_every_glob_spelling_finds_the_file(tmp_path: Path, rel: str):
    _write(tmp_path, rel, MATRIX_TEXT)
    row = artifact_gap_status(MATRIX, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_an_ordinary_markdown_file_is_not_evidence(tmp_path: Path):
    _write(tmp_path, "README.md", MATRIX_TEXT + _document(REALISTIC))
    assert artifact_gap_status(MATRIX, tmp_path).status == GapStatus.MISSING
    row = artifact_gap_status(f"{DESCRIPTION}#services", tmp_path)
    assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_description_empty_repo_is_missing(tmp_path: Path, clause: str):
    row = artifact_gap_status(f"{DESCRIPTION}#{clause}", tmp_path)
    assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_description_unrelated_sentence_is_partial_035(tmp_path: Path, clause: str):
    _write(tmp_path, "docs/system-description.md", _document({clause: UNRELATED}))
    row = artifact_gap_status(f"{DESCRIPTION}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_description_realistic_section_is_partial_06(tmp_path: Path, clause: str):
    _write(
        tmp_path,
        "docs/system-description.md",
        _document({clause: REALISTIC[clause]}),
    )
    row = artifact_gap_status(f"{DESCRIPTION}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize(
    "rel",
    [
        "system-description.md",
        "docs/system_description_2026.md",
        "docs/assurance/service-description.md",
    ],
)
def test_description_every_glob_spelling_finds_the_file(tmp_path: Path, rel: str):
    _write(tmp_path, rel, _document({"services": REALISTIC["services"]}))
    row = artifact_gap_status(f"{DESCRIPTION}#services", tmp_path)
    assert row.confidence == pytest.approx(0.6)


def test_a_full_description_is_partial_never_met(tmp_path: Path):
    _write(tmp_path, "docs/system-description.md", _document(REALISTIC))
    row = artifact_gap_status(DESCRIPTION, tmp_path)
    assert row.status == GapStatus.PARTIAL
