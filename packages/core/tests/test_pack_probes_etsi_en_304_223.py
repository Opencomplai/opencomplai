"""Pack-local probes of ETSI_EN_304_223: AI asset inventory and end-of-life note."""

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
    / "ETSI_EN_304_223"
    / "probes.json"
)
PREFIX = "etsi_en_304_223"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."

INVENTORY = "etsi_en_304_223.ai_asset_inventory"
END_OF_LIFE = "etsi_en_304_223.end_of_life_note"

# ref -> (matching paths, a short realistic file)
CASES = {
    INVENTORY: (
        (
            "docs/ai-asset-inventory.md",
            "docs/ai_asset_inventory.md",
            "model-inventory.md",
            "model_inventory.md",
            "docs/registers/ai-assets.md",
            "docs/ai_assets.md",
        ),
        "The ticket ranking model entry has the name rank-v2 and the type classifier. "
        "Its training dataset is the 2025 ticket export and the system prompts are kept "
        "in the prompt store. The owner is the support platform team at version 2.1.\n",
    ),
    END_OF_LIFE: (
        (
            "docs/decommission.md",
            "end-of-life.md",
            "docs/end_of_life.md",
            "docs/ai-disposal.md",
            "docs/ai_disposal-plan.md",
        ),
        "When the ranking system is retired we delete the training data and the stored "
        "configuration, and the model is archived or handed over to the next owner. "
        "We notify the users and the data controllers two weeks before the switch-off.\n",
    ),
}
REFS = tuple(CASES)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_file_parses_with_the_pack_prefix():
    parsed = parse_probe_file(PROBE_FILE, prefix=PREFIX)
    assert tuple(parsed) == REFS


def test_provenance_follows_the_heuristic_rule():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    assert data["family"] == "etsi_en_304_223"
    for ref in REFS:
        probe = data["probes"][ref]
        markers = probe["markers"]
        assert markers["body_only"] is True
        assert markers["forbid_scaffold"] is True
        assert len(markers["all"]) >= 3
        prov = probe["provenance"]
        assert prov["source"].startswith("heuristic (no legal source):")
        assert prov["confidence"] == "low"
        assert prov["needs_founder_review"] is True


def test_every_glob_has_its_underscore_twin_and_none_is_bare():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    for ref in REFS:
        patterns = data["probes"][ref]["patterns"]
        assert "**/*.md" not in patterns
        for pat in patterns:
            if "-" in pat:
                assert pat.replace("-", "_") in patterns


@pytest.mark.parametrize("ref", REFS)
def test_every_ref_exists(ref: str):
    assert probe_exists(ref)


@pytest.mark.parametrize("ref", REFS)
def test_an_empty_repo_is_missing(tmp_path: Path, ref: str):
    assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize("ref", REFS)
def test_a_matching_file_with_one_unrelated_sentence_is_partial_035(
    tmp_path: Path, ref: str
):
    _write(tmp_path, CASES[ref][0][0], UNRELATED)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("ref", REFS)
def test_a_short_realistic_file_is_partial_06_never_met(tmp_path: Path, ref: str):
    _write(tmp_path, CASES[ref][0][0], CASES[ref][1])
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize("ref", REFS)
def test_an_unfilled_scaffold_is_partial_035(tmp_path: Path, ref: str):
    _write(tmp_path, CASES[ref][0][0], CASES[ref][1] + SCAFFOLD_PLACEHOLDER + "\n")
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize(
    ("ref", "rel"),
    [(ref, rel) for ref in REFS for rel in CASES[ref][0]],
)
def test_every_glob_spelling_finds_the_file(tmp_path: Path, ref: str, rel: str):
    _write(tmp_path, rel, CASES[ref][1])
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize("ref", REFS)
def test_an_ordinary_markdown_file_is_not_evidence(tmp_path: Path, ref: str):
    _write(tmp_path, "README.md", CASES[ref][1])
    assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING
