"""Pack-local probes of ISO_IEC_42001: the statement of applicability."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.gap_probes import (
    SCAFFOLD_PLACEHOLDER,
    artifact_gap_status,
    probe_exists,
)
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import parse_probe_file

PROBE_FILE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "opencomplai_core"
    / "packs"
    / "ISO_IEC_42001"
    / "probes.json"
)
PREFIX = "iso_iec_42001"
REF = "iso_iec_42001.soa_justification"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."
REALISTIC = (
    "Control A.6.2 is included because the ranking model is built in house and "
    "we need the lifecycle controls. Control A.10.3 is excluded, and the reason "
    "is that we buy no AI components from suppliers.\n"
)
PATHS = (
    "statement-of-applicability.md",
    "docs/statement_of_applicability.md",
    "docs/statement-of-applicability-2026.md",
    "soa.md",
    "docs/soa-v2.md",
    "docs/aims/applicability.md",
)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_file_parses_with_the_pack_prefix():
    assert tuple(parse_probe_file(PROBE_FILE, prefix=PREFIX)) == (REF,)


def test_provenance_and_markers_follow_the_rules():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    assert data["family"] == "iso_iec_42001"
    probe = data["probes"][REF]
    assert probe["markers"]["body_only"] is True
    assert probe["markers"]["forbid_scaffold"] is True
    assert len(probe["markers"]["all"]) == 3
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


def test_the_ref_exists():
    assert probe_exists(REF)


def test_an_empty_repo_is_missing(tmp_path: Path):
    assert artifact_gap_status(REF, tmp_path).status == GapStatus.MISSING


def test_a_matching_file_with_one_unrelated_sentence_is_partial_035(tmp_path: Path):
    _write(tmp_path, PATHS[0], UNRELATED)
    row = artifact_gap_status(REF, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


def test_a_short_realistic_file_is_partial_06_never_met(tmp_path: Path):
    _write(tmp_path, PATHS[0], REALISTIC)
    row = artifact_gap_status(REF, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_an_unfilled_scaffold_is_partial_035(tmp_path: Path):
    _write(tmp_path, PATHS[0], REALISTIC + SCAFFOLD_PLACEHOLDER + "\n")
    row = artifact_gap_status(REF, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize(
    "text",
    [
        "Controls are included because we want them, and we justify each one.",
        "A.6.2 is part of the plan and we wrote it down for the board.",
    ],
)
def test_a_file_missing_a_marker_topic_is_partial_035(tmp_path: Path, text: str):
    _write(tmp_path, PATHS[0], text)
    row = artifact_gap_status(REF, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("rel", PATHS)
def test_every_glob_spelling_finds_the_file(tmp_path: Path, rel: str):
    _write(tmp_path, rel, REALISTIC)
    row = artifact_gap_status(REF, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_an_ordinary_markdown_file_is_not_evidence(tmp_path: Path):
    _write(tmp_path, "README.md", REALISTIC)
    assert artifact_gap_status(REF, tmp_path).status == GapStatus.MISSING
