"""Pack-local probes of ISO_IEC_27090: input filtering and model access configuration."""

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
    / "ISO_IEC_27090"
    / "probes.json"
)
PREFIX = "iso_iec_27090"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."

# ref -> (matching file, short realistic content)
CASES = {
    "iso_iec_27090.input_validation_config": (
        "config/guardrails.yaml",
        "input:\n  max_length: 4000\n  blocklist:\n    - ignore previous instructions\n",
    ),
    "iso_iec_27090.model_access_control": (
        "policy/model-access.yaml",
        "roles:\n  ml-engineer:\n    allow: [read, deploy]\n  analyst:\n    deny: [deploy]\n",
    ),
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_file_parses_with_the_pack_prefix():
    parsed = parse_probe_file(PROBE_FILE, prefix=PREFIX)
    assert set(parsed) == set(CASES)


def test_the_file_declares_the_family_and_provenance():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    assert data["family"] == "iso_iec_27090"
    for ref, probe in data["probes"].items():
        assert ref.startswith(PREFIX + ".")
        assert probe["markers"]["select"] is True
        prov = probe["provenance"]
        assert prov["source"].startswith("heuristic (no legal source):")
        assert prov["confidence"] == "low"
        assert prov["needs_founder_review"] is True


def test_every_glob_has_its_underscore_twin_and_none_is_bare():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    for probe in data["probes"].values():
        patterns = probe["patterns"]
        assert "**/*.md" not in patterns
        for pat in patterns:
            if "-" in pat:
                assert pat.replace("-", "_") in patterns


@pytest.mark.parametrize("ref", sorted(CASES))
def test_the_ref_exists(ref: str):
    assert probe_exists(ref)


@pytest.mark.parametrize("ref", sorted(CASES))
def test_an_empty_repo_is_missing(tmp_path: Path, ref: str):
    assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize("ref", sorted(CASES))
def test_a_matching_file_with_an_unrelated_sentence_is_not_selected(
    tmp_path: Path, ref: str
):
    # select probes only pick a file that carries the marker, so a file with
    # one unrelated sentence counts as no file: Missing, never Met
    _write(tmp_path, CASES[ref][0], UNRELATED)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("ref", sorted(CASES))
def test_a_short_realistic_file_is_partial_06_never_met(tmp_path: Path, ref: str):
    rel, text = CASES[ref]
    _write(tmp_path, rel, text)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize("ref", sorted(CASES))
def test_the_underscore_spelling_is_found(tmp_path: Path, ref: str):
    rel, text = CASES[ref]
    _write(tmp_path, rel.replace("-", "_"), text)
    row = artifact_gap_status(ref, tmp_path)
    assert row.confidence == pytest.approx(0.6)
