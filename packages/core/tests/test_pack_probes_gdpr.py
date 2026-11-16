"""Pack-local probes of GDPR: the data protection impact assessment, clause by clause."""

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
    / "GDPR"
    / "probes.json"
)
PREFIX = "gdpr"
DPIA = "gdpr.dpia"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."

CLAUSE_IDS = (
    "processing",
    "necessity",
    "risks",
    "measures",
    "consultation",
    "special-categories",
    "automated-decisions",
)

REALISTIC = {
    "processing": "We process customer support messages in order to route tickets to the right team.",
    "necessity": "The processing is necessary and proportionate because we keep only the fields routing needs.",
    "risks": "The main risk is that individuals could be exposed if a ticket is sent to the wrong team.",
    "measures": "Measures include encryption at rest, access control by role and a short retention period.",
    "consultation": "The data protection officer was consulted and no supervisory authority consultation is required.",
    "special-categories": "No special category data is collected; health details are removed before storage.",
    "automated-decisions": "The tool suggests a team but a human review confirms each decision, with no profiling.",
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _document(bodies: dict[str, str]) -> str:
    return "\n".join(f"<!-- clause: {c} -->\n{t}\n" for c, t in bodies.items())


def test_the_file_parses_with_the_pack_prefix():
    parsed = parse_probe_file(PROBE_FILE, prefix=PREFIX)
    assert set(parsed) == {DPIA}


def test_provenance_follows_the_heuristic_rule():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    assert data["family"] == "gdpr"
    assert tuple(data["probes"][DPIA]["clauses"]) == CLAUSE_IDS
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
    assert probe_exists(DPIA)
    for clause in CLAUSE_IDS:
        assert probe_exists(f"{DPIA}#{clause}")
    assert not probe_exists(f"{DPIA}#nothing")


def test_realistic_text_covers_every_clause():
    assert tuple(REALISTIC) == CLAUSE_IDS


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_clause_empty_repo_is_missing(tmp_path: Path, clause: str):
    assert artifact_gap_status(f"{DPIA}#{clause}", tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_clause_unrelated_sentence_is_partial_035(tmp_path: Path, clause: str):
    _write(tmp_path, "DPIA.md", _document({clause: UNRELATED}))
    row = artifact_gap_status(f"{DPIA}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_clause_realistic_section_is_partial_06(tmp_path: Path, clause: str):
    _write(tmp_path, "DPIA.md", _document(REALISTIC))
    row = artifact_gap_status(f"{DPIA}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize(
    "rel",
    [
        "DPIA.md",
        "docs/privacy/dpia-support.md",
        "data-protection-impact-assessment.md",
        "docs/data_protection_impact_assessment.md",
    ],
)
def test_every_glob_spelling_finds_the_file(tmp_path: Path, rel: str):
    _write(tmp_path, rel, _document(REALISTIC))
    row = artifact_gap_status(f"{DPIA}#processing", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)
