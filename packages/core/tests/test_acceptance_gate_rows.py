"""`acceptance_gate_failures`: which EU rows fail for an accepted high-risk system."""

from __future__ import annotations

import pytest
from opencomplai_core.frameworks import acceptance_gate_failures, validate_gate
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
)


def _report(statuses: dict[str, GapStatus]) -> GapReport:
    return GapReport(
        system_id="s",
        commit_ref="c",
        generated_at="2026-01-01T00:00:00Z",
        articles=[
            ArticleGapStatus(
                article=art,
                status=status,
                source=ArticleGapSource.RULE,
                evidence_ref="x",
            )
            for art, status in statuses.items()
        ],
    )


def test_missing_rows_exclude_art_6() -> None:
    report = _report(
        {
            "Art. 5": GapStatus.MET,
            "Art. 6": GapStatus.MISSING,
            "Art. 9": GapStatus.MISSING,
            "Art. 10": GapStatus.MISSING,
        }
    )
    assert acceptance_gate_failures(report) == ["Art. 9", "Art. 10"]


def test_unverified_and_met_never_fail() -> None:
    report = _report({"Art. 9": GapStatus.UNVERIFIED, "Art. 10": GapStatus.MET})
    assert acceptance_gate_failures(report) == []
    assert acceptance_gate_failures(report, "partial") == []


def test_partial_fails_only_with_fail_on_partial() -> None:
    report = _report({"Art. 9": GapStatus.PARTIAL})
    assert acceptance_gate_failures(report) == []
    assert acceptance_gate_failures(report, "partial") == ["Art. 9"]


def test_validate_gate_still_rejects_eu_ai_act() -> None:
    with pytest.raises(ValueError, match="EU_AI_ACT cannot be gated"):
        validate_gate(["EU_AI_ACT"], "missing", ["EU_AI_ACT"])
