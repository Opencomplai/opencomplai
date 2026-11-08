"""The `unverified` fail-on level of the framework gate.

With it, Missing and Partial rows fail as with `partial`, and so does an Unverified
row that only an attestation can decide: not attested, or attested and expired.
Rows another source can decide, NIST AI RMF rows and the EU AI Act never fail on
being Unverified.
"""

from __future__ import annotations

from datetime import date

import pytest
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    evaluate_targets,
    gate_failures,
    validate_gate,
)
from opencomplai_core.models import (
    Attestation,
    FrameworkInputs,
    GapStatus,
    SystemManifest,
)

TODAY = date(2026, 11, 3)
ISO = "ISO_IEC_27001"
NIST = "NIST_AI_RMF"
ROW = f"{ISO}:A.6.3"


def _att(**over: object) -> Attestation:
    base: dict[str, object] = {
        "statement": "Training runs every year.",
        "attested_by": "Jane Doe",
        "attested_at": "2026-06-01",
    }
    return Attestation.model_validate({**base, **over})


def _manifest(**inputs: FrameworkInputs) -> SystemManifest:
    return SystemManifest(
        system_id="sys", intended_purpose="credit scoring", framework_inputs=inputs
    )


def _iso_reports(attested: dict[str, Attestation] | None = None):
    manifest = _manifest(**{ISO: FrameworkInputs(attested=attested or {})})
    return evaluate_targets(manifest, [ISO], commit_ref="abc", today=TODAY)


def test_unverified_is_a_valid_level_for_a_native_pack() -> None:
    validate_gate([ISO], "unverified", [EU_AI_ACT, ISO])
    with pytest.raises(ValueError, match="missing, partial, unverified"):
        validate_gate([ISO], "everything", [EU_AI_ACT, ISO])
    with pytest.raises(ValueError, match="EU_AI_ACT cannot be gated"):
        validate_gate([EU_AI_ACT], "unverified", [EU_AI_ACT, ISO])


def test_the_gate_follows_an_attestation_through_its_expiry() -> None:
    assert ROW in gate_failures(_iso_reports(), [ISO], "unverified")
    assert ROW not in gate_failures(_iso_reports({ROW: _att()}), [ISO], "unverified")
    expired = _iso_reports({ROW: _att(valid_until=date(2026, 11, 2))})
    assert ROW in gate_failures(expired, [ISO], "unverified")


def test_the_levels_below_it_never_fail_an_unattested_row() -> None:
    for level in ("missing", "partial"):
        assert gate_failures(_iso_reports(), [ISO], level) == []


def test_every_iso_27001_row_fails_until_attested() -> None:
    reports = _iso_reports()
    every_row = [r.article for r in reports[ISO].report.articles]
    assert gate_failures(reports, [ISO], "unverified") == every_row


def test_a_mixed_row_is_not_failed_for_being_unverified() -> None:
    # ISO 42001 Clause 6.1.2 is capped by an artifact probe as well as an attestation.
    manifest = _manifest()
    reports = evaluate_targets(
        manifest, ["ISO_IEC_42001"], commit_ref="abc", today=TODAY
    )
    rows = {r.article: r for r in reports["ISO_IEC_42001"].report.articles}
    mixed = "ISO_IEC_42001:Clause 6.1.2"
    assert rows[mixed].status is GapStatus.UNVERIFIED
    failing = gate_failures(reports, ["ISO_IEC_42001"], "unverified")
    assert mixed not in failing
    assert "ISO_IEC_42001:Clause 4.1" in failing  # attestation-only


def test_a_row_with_a_supporting_probe_is_still_attestation_only() -> None:
    # 27090:5.5 also has a supporting artifact probe (it only points at a file);
    # 27090:5.7 has an evaluator, so it can be decided by something else.
    reports = evaluate_targets(
        _manifest(), ["ISO_IEC_27090"], commit_ref="abc", today=TODAY
    )
    failing = gate_failures(reports, ["ISO_IEC_27090"], "unverified")
    assert "ISO_IEC_27090:5.5" in failing
    assert "ISO_IEC_27090:5.7" not in failing


def test_nist_is_never_failed_for_being_unverified() -> None:
    reports = evaluate_targets(_manifest(), [NIST], commit_ref="abc", today=TODAY)
    rows = reports[NIST].report.articles
    assert any(r.status is GapStatus.UNVERIFIED for r in rows)
    assert gate_failures(reports, [NIST], "unverified") == gate_failures(
        reports, [NIST], "partial"
    )
