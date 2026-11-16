"""The third_parties probes against the empty, scaffolded and evidenced fixture repos."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.gap_probes import artifact_gap_status, run_artifact_probe
from opencomplai_core.models import GapStatus

SCAFFOLDS = (
    Path(__file__).parents[1] / "src/opencomplai_core/probes/scaffolds/third_parties"
)
FIXTURES = Path(__file__).parent / "fixtures/probes/third_parties"
INDEX = json.loads((SCAFFOLDS / "index.json").read_text(encoding="utf-8"))
DOCUMENT_REFS = ["vendor_register", "contract_checklist", "exit_plan"]
REFS = DOCUMENT_REFS  # no config probes in this family


def test_index_covers_every_document_probe():
    assert sorted(INDEX) == sorted(DOCUMENT_REFS)


@pytest.mark.parametrize("ref", REFS)
def test_empty_is_missing(ref: str):
    row = artifact_gap_status(ref, FIXTURES / "empty")
    assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("ref", REFS)
def test_scaffolded_is_partial_unfilled(ref: str):
    row = artifact_gap_status(ref, FIXTURES / "scaffolded")
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)
    assert "unfilled" in row.rationale


@pytest.mark.parametrize("ref", REFS)
def test_evidenced_is_partial_06(ref: str):
    row = artifact_gap_status(ref, FIXTURES / "evidenced")
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize("ref", DOCUMENT_REFS)
def test_scaffolded_file_equals_scaffold(ref: str):
    target = INDEX[ref]["target"]
    assert (FIXTURES / "scaffolded" / target).read_bytes() == (
        SCAFFOLDS / f"{ref}.md"
    ).read_bytes()
    assert len((SCAFFOLDS / f"{ref}.md").read_text(encoding="utf-8").splitlines()) <= 60


@pytest.mark.parametrize("ref", DOCUMENT_REFS)
def test_target_is_found_in_evidenced(ref: str):
    target = INDEX[ref]["target"]
    result = run_artifact_probe(ref, FIXTURES / "evidenced")
    assert target in result.found_paths
    assert "_fill in_" not in (FIXTURES / "evidenced" / target).read_text(
        encoding="utf-8"
    )
