"""Pack-local probes of NIST_AI_RMF: one AI RMF profile read function by function."""

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
    / "NIST_AI_RMF"
    / "probes.json"
)
PREFIX = "nist_ai_rmf"
REF = "nist_ai_rmf.profile"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."
FUNCTIONS = ("govern", "map", "measure", "manage")

REALISTIC = {
    "govern": "Currently our policy and oversight sit with the risk board; the target is named accountability for every system.",
    "map": "Today the context and intended use are written per system; the target state adds stakeholders for each purpose.",
    "measure": "Current metrics are tested once a year; the goal is continuous testing and evaluation of every release.",
    "manage": "At present we monitor and respond to incidents ad hoc; the target is a tracked mitigation plan for each risk.",
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


def test_the_file_declares_the_family_and_every_function():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    assert data["family"] == "nist_ai_rmf"
    probe = data["probes"][REF]
    assert probe["type"] == "clause_document"
    assert probe["noun"] == "AI RMF profile"
    assert tuple(probe["clauses"]) == FUNCTIONS
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


def test_the_ref_and_every_clause_ref_exist():
    assert probe_exists(REF)
    for fn in FUNCTIONS:
        assert probe_exists(f"{REF}#{fn}")
    assert not probe_exists(f"{REF}#other")


def test_realistic_text_covers_every_function():
    assert tuple(REALISTIC) == FUNCTIONS


@pytest.mark.parametrize("fn", FUNCTIONS)
def test_an_empty_repo_is_missing(tmp_path: Path, fn: str):
    assert artifact_gap_status(f"{REF}#{fn}", tmp_path).status == GapStatus.MISSING


def test_an_empty_repo_is_not_met_for_the_whole_document(tmp_path: Path):
    assert artifact_gap_status(REF, tmp_path).status != GapStatus.MET


@pytest.mark.parametrize("fn", FUNCTIONS)
def test_a_section_with_one_unrelated_sentence_is_partial_035(tmp_path: Path, fn: str):
    _write(tmp_path, "AI_RMF_PROFILE.md", _document({fn: UNRELATED}))
    row = artifact_gap_status(f"{REF}#{fn}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("fn", FUNCTIONS)
def test_a_file_without_the_anchor_is_partial_035(tmp_path: Path, fn: str):
    _write(tmp_path, "AI_RMF_PROFILE.md", UNRELATED)
    row = artifact_gap_status(f"{REF}#{fn}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("fn", FUNCTIONS)
def test_a_short_realistic_section_is_partial_06_never_met(tmp_path: Path, fn: str):
    _write(tmp_path, "AI_RMF_PROFILE.md", _document({fn: REALISTIC[fn]}))
    row = artifact_gap_status(f"{REF}#{fn}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize("fn", FUNCTIONS)
def test_a_section_with_only_a_current_state_is_unfilled(tmp_path: Path, fn: str):
    body = REALISTIC[fn].split(";")[0] + "."
    _write(tmp_path, "AI_RMF_PROFILE.md", _document({fn: body}))
    row = artifact_gap_status(f"{REF}#{fn}", tmp_path)
    assert row.confidence == pytest.approx(0.35)


def test_a_full_document_is_partial_never_met(tmp_path: Path):
    _write(tmp_path, "AI_RMF_PROFILE.md", _document(REALISTIC))
    assert artifact_gap_status(REF, tmp_path).status == GapStatus.PARTIAL


@pytest.mark.parametrize(
    "rel",
    [
        "AI_RMF_PROFILE.md",
        "docs/ai-rmf-profile.md",
        "docs/ai_rmf_profile.md",
        "docs/x/ai-rmf-profile-2026.md",
        "x/ai_rmf_profile.md",
    ],
)
def test_every_glob_spelling_finds_the_file(tmp_path: Path, rel: str):
    _write(tmp_path, rel, _document({"govern": REALISTIC["govern"]}))
    row = artifact_gap_status(f"{REF}#govern", tmp_path)
    assert row.confidence == pytest.approx(0.6)


def test_an_ordinary_markdown_file_is_not_evidence(tmp_path: Path):
    _write(tmp_path, "README.md", _document(REALISTIC))
    assert artifact_gap_status(f"{REF}#govern", tmp_path).status == GapStatus.MISSING
