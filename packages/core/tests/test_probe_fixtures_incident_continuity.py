"""The incident_continuity probes against three fixture repositories and the shared scaffolds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.gap_probes import artifact_gap_status, run_artifact_probe
from opencomplai_core.models import GapStatus

CORE = Path(__file__).resolve().parents[1]
FIXTURES = CORE / "tests" / "fixtures" / "probes" / "incident_continuity"
SCAFFOLDS = (
    CORE / "src" / "opencomplai_core" / "probes" / "scaffolds" / "incident_continuity"
)
PROBES = json.loads(
    (
        CORE / "src" / "opencomplai_core" / "probes" / "incident_continuity.json"
    ).read_text(encoding="utf-8")
)["probes"]
INDEX: dict[str, dict[str, str]] = json.loads(
    (SCAFFOLDS / "index.json").read_text(encoding="utf-8")
)
REFS = tuple(PROBES)
REPOS = ("empty", "scaffolded", "evidenced")


def _doc_probe(ref: str) -> bool:
    return "markers" in PROBES[ref]


def _expected(ref: str, repo: str) -> tuple[GapStatus, float]:
    if repo == "empty":
        return GapStatus.MISSING, 0.4
    if repo == "scaffolded":
        if _doc_probe(ref):
            return GapStatus.PARTIAL, 0.35
        return GapStatus.MISSING, 0.4
    return GapStatus.PARTIAL, 0.6


def test_index_covers_exactly_the_document_probes():
    assert set(INDEX) == {ref for ref in REFS if _doc_probe(ref)}


@pytest.mark.parametrize("repo", REPOS)
@pytest.mark.parametrize("ref", REFS)
def test_status_and_confidence(ref: str, repo: str):
    row = artifact_gap_status(ref, FIXTURES / repo)
    status, confidence = _expected(ref, repo)
    assert row.status == status
    assert status != GapStatus.MET
    assert row.confidence == confidence
    if repo == "scaffolded" and _doc_probe(ref):
        assert "unfilled" in row.rationale


@pytest.mark.parametrize("ref", sorted(INDEX))
def test_scaffold_shape(ref: str):
    text = (SCAFFOLDS / f"{ref}.md").read_text(encoding="utf-8")
    assert "_fill in_" in text
    assert len(text.splitlines()) <= 60


@pytest.mark.parametrize("ref", sorted(INDEX))
def test_scaffolded_file_is_the_scaffold_unchanged(ref: str):
    target = FIXTURES / "scaffolded" / INDEX[ref]["target"]
    scaffold = SCAFFOLDS / f"{ref}.md"
    assert target.read_bytes() == scaffold.read_bytes()


@pytest.mark.parametrize("ref", sorted(INDEX))
def test_target_is_found_in_evidenced(ref: str):
    target = INDEX[ref]["target"]
    result = run_artifact_probe(ref, FIXTURES / "evidenced")
    assert target in result.found_paths
    assert result.content_markers_met is True
    assert "_fill in_" not in (FIXTURES / "evidenced" / target).read_text(
        encoding="utf-8"
    )


def test_empty_repo_holds_only_the_keep_file():
    assert [p.name for p in (FIXTURES / "empty").rglob("*") if p.is_file()] == [
        ".gitkeep"
    ]
