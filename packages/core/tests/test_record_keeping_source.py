"""Art. 12 record_keeping_declaration source: a declaration is PARTIAL at best."""

from __future__ import annotations

import re

from opencomplai_core.dossier_generator import (
    RECORD_KEEPING_REVIEW_NOTE,
    record_keeping_gap_status,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ConfidenceLabel,
    GapStatus,
    RecordKeeping,
    SystemManifest,
)


def _manifest(block: RecordKeeping | None = None) -> SystemManifest:
    return SystemManifest(
        system_id="t",
        intended_purpose="chatbot",
        compliance_target="EU_AI_ACT",
        commit_ref="abc123",
        record_keeping=block,
    )


def test_declared_logging_is_partial_never_met():
    row = record_keeping_gap_status(
        _manifest(RecordKeeping(logging_enabled=True, log_retention_days=90))
    )
    assert row is not None
    assert row.status == GapStatus.PARTIAL
    assert row.source == ArticleGapSource.MANIFEST
    assert row.evidence_ref == "manifest:record_keeping_declaration"
    assert row.article == ""
    assert row.confidence is None
    assert row.confidence_label == ConfidenceLabel.NOT_ASSESSED


def test_declared_no_logging_is_missing():
    row = record_keeping_gap_status(_manifest(RecordKeeping(logging_enabled=False)))
    assert row is not None
    assert row.status == GapStatus.MISSING


def test_no_block_gives_no_candidate():
    assert record_keeping_gap_status(_manifest()) is None


def test_rationale_has_no_dates_and_review_note_is_flagged():
    row = record_keeping_gap_status(
        _manifest(RecordKeeping(logging_enabled=True, log_retention_days=90))
    )
    assert "retention declared yes" in row.rationale
    assert not re.search(r"\d", row.rationale)
    assert RECORD_KEEPING_REVIEW_NOTE["needs_founder_review"] is True
    assert RECORD_KEEPING_REVIEW_NOTE["confidence"] == "low"
    assert RECORD_KEEPING_REVIEW_NOTE["source"]
