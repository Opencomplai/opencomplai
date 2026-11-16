"""EU AI Act reference behaviour of the artifact probes over three fixture repos.

Nothing on disk reads Missing; an unfilled scaffold reads Partial (low
confidence); a filled document reads Partial (higher confidence). An artifact
probe never gives Met.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.gap_probes import QMS_17_1_CLAUSES, artifact_gap_status
from opencomplai_core.models import GapStatus

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "packs" / "EU_AI_ACT"

REFS = ["post_market_monitoring_plan", *(ref for _, ref, _ in QMS_17_1_CLAUSES)]

# repo -> (status, confidence)
EXPECTED = {
    "empty": (GapStatus.MISSING, 0.4),
    "scaffolded": (GapStatus.PARTIAL, 0.35),
    "evidenced": (GapStatus.PARTIAL, 0.6),
}


def test_fourteen_refs() -> None:
    assert len(REFS) == 14
    assert len(set(REFS)) == 14


@pytest.mark.parametrize("repo", sorted(EXPECTED))
@pytest.mark.parametrize("ref", REFS)
def test_artifact_probe_reference_outcome(ref: str, repo: str) -> None:
    status, confidence = EXPECTED[repo]
    row = artifact_gap_status(ref, FIXTURES / repo)
    assert row.status == status, row.rationale
    assert row.status != GapStatus.MET
    assert row.confidence == confidence, row.rationale
    if repo == "scaffolded":
        assert "unfilled" in row.rationale


def test_fixture_directory_has_no_manifest() -> None:
    assert FIXTURES.is_dir()
    assert not (FIXTURES / "manifest.json").exists()
    assert not list(FIXTURES.rglob("manifest.json"))
