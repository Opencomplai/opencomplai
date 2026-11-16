"""Pack-local probes of ISO_IEC_23894: one AI risk management procedure read clause by clause."""

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
    / "ISO_IEC_23894"
    / "probes.json"
)
PREFIX = "iso_iec_23894"
REF = "iso_iec_23894.risk_process"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."

CLAUSE_IDS = (
    "6.2",
    "6.3.2",
    "6.3.3",
    "6.3.4",
    "6.4.2",
    "6.4.3",
    "6.4.4",
    "6.5.2",
    "6.5.3",
    "6.6",
    "6.7",
)

# clause id -> a short realistic section body
REALISTIC = {
    "6.2": "We communicate with and consult the stakeholders on each risk exercise, and the exchanges are recorded in the log.",
    "6.3.2": "The scope covers the ticket ranking system; the billing tools are out of scope and the boundary is agreed before work starts.",
    "6.3.3": "The external context includes customer rules and regulators; the internal context is our team structure and the model's purpose.",
    "6.3.4": "The criteria use a scale of low, medium and high for each risk level, and the risk lead gives approval before assessment.",
    "6.4.2": "We identify risks and list their sources and consequences in the register, such as biased ranking of urgent tickets.",
    "6.4.3": "Each risk is analysed for its likelihood and severity so that the level of every entry in the register is understood.",
    "6.4.4": "We evaluate every analysed risk by comparing it with the criteria, then prioritise the ones that need treatment first.",
    "6.5.2": "For each risk the chosen treatment option is to avoid, reduce, share or accept it, and the reasons are written down.",
    "6.5.3": "A treatment plan names an owner and a deadline, we implement it, and the residual risk is reviewed after it is done.",
    "6.6": "We monitor the risks and review the process every quarter, and the findings are fed back as feedback to the team.",
    "6.7": "The process and its outcomes are recorded and the report goes to the board through the management reporting channels.",
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
    assert data["family"] == "iso_iec_23894"
    probe = data["probes"][REF]
    assert probe["type"] == "clause_document"
    assert probe["noun"] == "AI risk management procedure"
    assert tuple(probe["clauses"]) == CLAUSE_IDS
    prov = probe["provenance"]
    assert prov["source"].startswith("heuristic (no legal source):")
    assert prov["confidence"] == "low"
    assert prov["needs_founder_review"] is True


def test_every_glob_has_its_underscore_twin_and_none_is_bare():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    patterns = data["probes"][REF]["patterns"]
    assert "AI_RISK_MANAGEMENT.md" in patterns
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


def test_an_empty_repo_is_not_met_for_the_whole_document(tmp_path: Path):
    row = artifact_gap_status(REF, tmp_path)
    assert row.status != GapStatus.MET


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_section_with_one_unrelated_sentence_is_partial_035(
    tmp_path: Path, clause: str
):
    _write(tmp_path, "AI_RISK_MANAGEMENT.md", _document({clause: UNRELATED}))
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_file_without_the_clause_anchor_is_partial_035(tmp_path: Path, clause: str):
    _write(tmp_path, "AI_RISK_MANAGEMENT.md", UNRELATED)
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_short_realistic_section_is_partial_06_never_met(tmp_path: Path, clause: str):
    _write(
        tmp_path,
        "AI_RISK_MANAGEMENT.md",
        _document({clause: REALISTIC[clause]}),
    )
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_a_full_document_is_partial_never_met(tmp_path: Path):
    _write(tmp_path, "AI_RISK_MANAGEMENT.md", _document(REALISTIC))
    row = artifact_gap_status(REF, tmp_path)
    assert row.status == GapStatus.PARTIAL


@pytest.mark.parametrize(
    "rel",
    [
        "AI_RISK_MANAGEMENT.md",
        "docs/ai-risk-management.md",
        "docs/ai_risk_management.md",
        "docs/rm/ai-risk-management-2026.md",
        "x/ai_risk_management.md",
    ],
)
def test_every_glob_spelling_finds_the_file(tmp_path: Path, rel: str):
    _write(tmp_path, rel, _document({"6.6": REALISTIC["6.6"]}))
    row = artifact_gap_status(f"{REF}#6.6", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_an_ordinary_markdown_file_is_not_evidence(tmp_path: Path):
    _write(tmp_path, "README.md", _document(REALISTIC))
    row = artifact_gap_status(f"{REF}#6.6", tmp_path)
    assert row.status == GapStatus.MISSING
