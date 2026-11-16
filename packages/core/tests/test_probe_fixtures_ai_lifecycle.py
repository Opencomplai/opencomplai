"""The ai_lifecycle probes against three fixture repositories: empty, scaffolded, evidenced."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.gap_probes import artifact_gap_status, run_artifact_probe
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import parse_probe_file

CORE = Path(__file__).resolve().parents[1]
PROBE_FILE = CORE / "src" / "opencomplai_core" / "probes" / "ai_lifecycle.json"
SCAFFOLDS = CORE / "src" / "opencomplai_core" / "probes" / "scaffolds" / "ai_lifecycle"
FIXTURES = CORE / "tests" / "fixtures" / "probes" / "ai_lifecycle"

REFS = tuple(parse_probe_file(PROBE_FILE))
INDEX = json.loads((SCAFFOLDS / "index.json").read_text(encoding="utf-8"))
REPOS = ("empty", "scaffolded", "evidenced")


def test_the_index_covers_the_document_probes():
    assert set(INDEX) == set(REFS)


@pytest.mark.parametrize("ref", REFS)
@pytest.mark.parametrize("repo", REPOS)
def test_status_and_confidence(ref: str, repo: str):
    row = artifact_gap_status(ref, FIXTURES / repo)
    assert row.status != GapStatus.MET
    if repo == "empty":
        assert row.status == GapStatus.MISSING
        return
    if repo == "scaffolded" and ref not in INDEX:
        assert row.status == GapStatus.MISSING
        return
    assert row.status == GapStatus.PARTIAL
    expected = 0.35 if repo == "scaffolded" else 0.6
    assert row.confidence == pytest.approx(expected)
    if repo == "scaffolded":
        assert "unfilled" in row.rationale


@pytest.mark.parametrize("ref", sorted(INDEX))
def test_the_scaffolded_file_is_the_scaffold_byte_for_byte(ref: str):
    scaffold = (SCAFFOLDS / f"{ref}.md").read_bytes()
    assert (FIXTURES / "scaffolded" / INDEX[ref]["target"]).read_bytes() == scaffold
    assert len(scaffold.decode("utf-8").splitlines()) <= 60


@pytest.mark.parametrize("ref", sorted(INDEX))
def test_every_target_is_found_in_the_evidenced_repo(ref: str):
    result = run_artifact_probe(ref, FIXTURES / "evidenced")
    assert INDEX[ref]["target"] in result.found_paths


def test_the_empty_repo_holds_only_a_gitkeep():
    assert [p.name for p in (FIXTURES / "empty").rglob("*")] == [".gitkeep"]
