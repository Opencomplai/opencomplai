"""privacy_records probes against the empty, scaffolded and evidenced fixture repositories."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core import gap_probes
from opencomplai_core.gap_probes import artifact_gap_status, run_artifact_probe
from opencomplai_core.models import GapStatus

CORE = Path(gap_probes.__file__).parent
SCAFFOLDS = CORE / "probes" / "scaffolds" / "privacy_records"
FIXTURES = Path(__file__).parent / "fixtures" / "probes" / "privacy_records"
INDEX = json.loads((SCAFFOLDS / "index.json").read_text(encoding="utf-8"))
PROBES = json.loads(
    (CORE / "probes" / "privacy_records.json").read_text(encoding="utf-8")
)["probes"]
REFS = sorted(PROBES)


def test_every_probe_has_a_scaffold():
    assert sorted(INDEX) == REFS
    for ref in REFS:
        assert (SCAFFOLDS / f"{ref}.md").is_file()


@pytest.mark.parametrize("ref", REFS)
def test_scaffold_shape(ref: str):
    lines = (SCAFFOLDS / f"{ref}.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 60
    assert "_fill in_" in lines
    assert INDEX[ref]["title"]


@pytest.mark.parametrize("ref", REFS)
def test_empty_is_missing(ref: str):
    assert artifact_gap_status(ref, FIXTURES / "empty").status == GapStatus.MISSING


@pytest.mark.parametrize("ref", REFS)
def test_scaffolded_is_partial_035_unfilled(ref: str):
    row = artifact_gap_status(ref, FIXTURES / "scaffolded")
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35
    assert "unfilled" in row.rationale


@pytest.mark.parametrize("ref", REFS)
def test_evidenced_is_partial_06(ref: str):
    row = artifact_gap_status(ref, FIXTURES / "evidenced")
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.6


@pytest.mark.parametrize("ref", REFS)
def test_scaffolded_file_is_byte_equal_to_scaffold(ref: str):
    target = INDEX[ref]["target"]
    assert (FIXTURES / "scaffolded" / target).read_bytes() == (
        SCAFFOLDS / f"{ref}.md"
    ).read_bytes()


@pytest.mark.parametrize("ref", REFS)
def test_target_is_found_in_evidenced(ref: str):
    result = run_artifact_probe(ref, FIXTURES / "evidenced")
    assert INDEX[ref]["target"] in [
        str(x).replace("\\", "/") for x in result.found_paths
    ]


def test_evidenced_has_no_placeholder():
    for path in (FIXTURES / "evidenced").rglob("*.md"):
        assert "_fill in_" not in path.read_text(encoding="utf-8")
