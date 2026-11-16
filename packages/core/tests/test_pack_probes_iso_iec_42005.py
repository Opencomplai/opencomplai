"""Pack-local probes of ISO_IEC_42005: one impact assessment read clause by clause."""

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
    / "ISO_IEC_42005"
    / "probes.json"
)
PREFIX = "iso_iec_42005"
REF = "iso_iec_42005.impact_assessment"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."

CLAUSE_IDS = (
    "5.2",
    "5.4",
    "5.5",
    "5.6",
    "5.7",
    "5.10",
    "5.11",
    "5.12",
    "6.2",
    "6.3",
    "6.4",
    "6.5",
    "6.6",
    "6.7",
    "6.8.2",
    "6.8.3",
    "6.9",
)

# clause id -> a short realistic section body
REALISTIC = {
    "5.2": "Our written assessment process is kept current by the governance team and every owner can find the procedure.",
    "5.4": "An assessment is triggered at each life-cycle stage and again before any major change to the ranking model.",
    "5.5": "The scope covers the ticket ranking system and its uses; the billing tools are out of scope for this review.",
    "5.6": "The service owner holds the role of assessor and the risk lead has the authority to review and sign-off each result.",
    "5.7": "Uses touching minors are restricted; a severity scale of low, medium and high rates every impact and sets the threshold.",
    "5.10": "Results are recorded in the register and the report is shared with the board and the stakeholders who asked for it.",
    "5.11": "The head of operations gives approval and the record shows who signed off, with the date, on each assessment.",
    "5.12": "We review each assessment every quarter and after each change, and we monitor whether the process still works.",
    "6.2": "This assessment covers the ticket ranking system, its current uses and the period from January to December.",
    "6.3": "The purpose is to rank support tickets; intended use is triage and a misuse such as automatic refusal is not intended.",
    "6.4": "The system relies on three years of ticket data, and we run quality checks for bias and completeness on that data.",
    "6.5": "The model is a gradient boosted classifier that our own team trained on labelled tickets with a documented algorithm.",
    "6.6": "The system is deployed in the cloud for agents in two countries; languages are English and French with a latency constraint.",
    "6.7": "Affected people are customers who write in; other stakeholders include agents, the legal team and the regulator.",
    "6.8.2": "The benefits are faster replies for customers, while the harms include urgent tickets being ranked too low by mistake.",
    "6.8.3": "If the ranking fails, urgent tickets wait longer; a foreseeable misuse is gaming the subject line to jump the queue.",
    "6.9": "We chose measures to reduce harm, such as a manual override, and the service owner tracks each action until it is done.",
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
    assert data["family"] == "iso_iec_42005"
    probe = data["probes"][REF]
    assert probe["type"] == "clause_document"
    assert tuple(probe["clauses"]) == CLAUSE_IDS
    prov = probe["provenance"]
    assert prov["source"].startswith("heuristic (no legal source):")
    assert prov["confidence"] == "low"
    assert prov["needs_founder_review"] is True


def test_every_glob_has_its_underscore_or_hyphen_twin_and_none_is_bare():
    patterns = json.loads(PROBE_FILE.read_text(encoding="utf-8"))["probes"][REF][
        "patterns"
    ]
    assert "**/*.md" not in patterns
    for pat in patterns:
        if "-" in pat:
            assert pat.replace("-", "_") in patterns


def test_the_ref_and_every_clause_ref_exist():
    assert probe_exists(REF)
    for clause in CLAUSE_IDS:
        assert probe_exists(f"{REF}#{clause}")
    assert not probe_exists(f"{REF}#9.9")


def test_realistic_text_covers_every_clause():
    assert tuple(REALISTIC) == CLAUSE_IDS


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_an_empty_repo_is_missing(tmp_path: Path, clause: str):
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.MISSING


def test_an_empty_repo_is_missing_for_the_whole_document(tmp_path: Path):
    # the bare ref is Partial with a count when the file is absent only if rows say so
    row = artifact_gap_status(REF, tmp_path)
    assert row.status != GapStatus.MET


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_section_with_one_unrelated_sentence_is_partial_035(
    tmp_path: Path, clause: str
):
    _write(tmp_path, "AI_IMPACT_ASSESSMENT.md", _document({clause: UNRELATED}))
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_file_without_the_clause_anchor_is_partial_035(tmp_path: Path, clause: str):
    _write(tmp_path, "AI_IMPACT_ASSESSMENT.md", UNRELATED)
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_short_realistic_section_is_partial_06_never_met(tmp_path: Path, clause: str):
    _write(
        tmp_path,
        "AI_IMPACT_ASSESSMENT.md",
        _document({clause: REALISTIC[clause]}),
    )
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_a_full_document_is_partial_never_met(tmp_path: Path):
    _write(tmp_path, "AI_IMPACT_ASSESSMENT.md", _document(REALISTIC))
    row = artifact_gap_status(REF, tmp_path)
    assert row.status == GapStatus.PARTIAL


@pytest.mark.parametrize(
    "rel",
    [
        "AI_IMPACT_ASSESSMENT.md",
        "docs/ai-impact-assessment.md",
        "docs/ai_impact_assessment.md",
        "docs/ia/ai-impact-assessment-2026.md",
        "x/ai_impact_assessment.md",
    ],
)
def test_every_glob_spelling_finds_the_file(tmp_path: Path, rel: str):
    _write(tmp_path, rel, _document({"6.9": REALISTIC["6.9"]}))
    row = artifact_gap_status(f"{REF}#6.9", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_an_ordinary_markdown_file_is_not_evidence(tmp_path: Path):
    _write(tmp_path, "README.md", _document(REALISTIC))
    row = artifact_gap_status(f"{REF}#6.9", tmp_path)
    assert row.status == GapStatus.MISSING
