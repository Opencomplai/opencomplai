"""Attestation `valid_until`, the `#<record_id>` suffix on evidence_ref, the new
optional fields' serialisation and the stale-attestation warning.

An attestation is current through its `valid_until` day and Unverified from the
next day on. Without `valid_until` nothing changes.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from opencomplai_core.frameworks import evaluate_targets
from opencomplai_core.gap_report import (
    build_gap_report,
    stale_attestation_warnings,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    Attestation,
    ConfidenceLabel,
    FrameworkInputs,
    GapReport,
    GapStatus,
    SystemManifest,
)
from opencomplai_core.nist_rmf_report import (
    build_nist_rmf_report,
    nist_rmf_as_gap_report,
)
from pydantic import ValidationError

ISO = "ISO_IEC_27001"
ROW = f"{ISO}:A.6.3"
TODAY = date(2026, 11, 3)
SHA = "a" * 64


def _att(**over: object) -> Attestation:
    base: dict[str, object] = {
        "statement": "Training is run every year and completion is recorded.",
        "attested_by": "Jane Doe",
        "attested_at": "2026-06-01",
    }
    return Attestation.model_validate({**base, **over})


def _iso_row(att: Attestation | None, today: date = TODAY) -> ArticleGapStatus:
    manifest = SystemManifest(
        system_id="sys",
        intended_purpose="credit scoring",
        framework_inputs={ISO: FrameworkInputs(attested={ROW: att} if att else {})},
    )
    reports = evaluate_targets(manifest, [ISO], commit_ref="abc", today=today)
    return next(r for r in reports[ISO].report.articles if r.article == ROW)


# --- expiry ------------------------------------------------------------------


def test_in_date_attestation_is_met() -> None:
    row = _iso_row(_att(valid_until=date(2026, 12, 31)))
    assert row.status is GapStatus.MET
    assert row.confidence_label is ConfidenceLabel.ATTESTED
    assert row.evidence_ref == "attestation:Jane Doe@2026-06-01"


def test_valid_until_is_the_last_good_day() -> None:
    assert _iso_row(_att(valid_until=TODAY)).status is GapStatus.MET
    assert _iso_row(_att(valid_until=TODAY - timedelta(days=1))).status is (
        GapStatus.UNVERIFIED
    )


def test_expired_attestation_is_unverified_and_keeps_its_reference() -> None:
    row = _iso_row(_att(valid_until=date(2026, 10, 31)))
    assert row.status is GapStatus.UNVERIFIED
    assert row.source is ArticleGapSource.ATTESTATION
    assert row.confidence is None
    assert row.confidence_label is ConfidenceLabel.NOT_ASSESSED
    assert row.evidence_ref == "attestation:Jane Doe@2026-06-01"
    assert row.rationale == (
        "Attestation expired on 2026-10-31. Renew it under "
        f"framework_inputs.{ISO}.attested in the manifest."
    )


def test_an_expired_bundle_record_is_renewed_by_re_attesting_the_record() -> None:
    row = _iso_row(_att(valid_until=date(2026, 10, 31), record_id="rec-1"))
    assert row.status is GapStatus.UNVERIFIED
    assert row.evidence_ref == "attestation:Jane Doe@2026-06-01#rec-1"
    assert row.rationale == (
        "Attestation expired on 2026-10-31. Re-attest the record to renew it."
    )
    assert "manifest" not in row.rationale


def test_no_valid_until_never_expires() -> None:
    old = _att(attested_at="2019-01-01")
    assert _iso_row(old).status is GapStatus.MET


def test_expiry_reaches_build_gap_report_directly() -> None:
    requirements = {
        ROW: {"title": "t", "sources": [{"kind": "attestation", "ref": ROW}]}
    }
    kwargs = {
        "system_id": "s",
        "commit_ref": "abc",
        "requirements": requirements,
        "today": TODAY,
    }
    live = build_gap_report(
        **kwargs, attestations={ROW: _att(valid_until=date(2026, 11, 3))}
    )
    dead = build_gap_report(
        **kwargs, attestations={ROW: _att(valid_until=date(2026, 11, 2))}
    )
    assert live.articles[0].status is GapStatus.MET
    assert dead.articles[0].status is GapStatus.UNVERIFIED


def test_an_unprefixed_eu_id_names_the_eu_ai_act_key_in_both_messages() -> None:
    requirements = {
        "Art. 4": {"title": "t", "sources": [{"kind": "attestation", "ref": "Art. 4"}]}
    }
    kwargs = {
        "system_id": "s",
        "commit_ref": "abc",
        "requirements": requirements,
        "today": TODAY,
    }
    missing = build_gap_report(**kwargs).articles[0]
    expired = build_gap_report(
        **kwargs, attestations={"Art. 4": _att(valid_until=date(2026, 1, 1))}
    ).articles[0]
    assert missing.rationale == (
        "No attestation recorded. Add one under "
        "framework_inputs.EU_AI_ACT.attested in the manifest."
    )
    assert expired.rationale == (
        "Attestation expired on 2026-01-01. Renew it under "
        "framework_inputs.EU_AI_ACT.attested in the manifest."
    )


def test_the_default_evaluation_date_is_the_current_utc_day() -> None:
    manifest = SystemManifest(
        system_id="sys",
        intended_purpose="x",
        framework_inputs={
            ISO: FrameworkInputs(
                attested={
                    ROW: _att(valid_until=date(2000, 1, 1)),
                    f"{ISO}:A.6.4": _att(valid_until=datetime.now(UTC).date()),
                }
            )
        },
    )
    rows = {
        r.article: r
        for r in evaluate_targets(manifest, [ISO], commit_ref="abc")[
            ISO
        ].report.articles
    }
    assert rows[ROW].status is GapStatus.UNVERIFIED
    assert rows[f"{ISO}:A.6.4"].status is GapStatus.MET


# --- record id ---------------------------------------------------------------


def test_record_id_is_appended_to_evidence_ref() -> None:
    met = _iso_row(_att(record_id="rec_01"))
    assert met.evidence_ref == "attestation:Jane Doe@2026-06-01#rec_01"
    expired = _iso_row(_att(record_id="rec_01", valid_until=date(2026, 1, 1)))
    assert expired.status is GapStatus.UNVERIFIED
    assert expired.evidence_ref == "attestation:Jane Doe@2026-06-01#rec_01"


def test_without_a_record_id_the_evidence_ref_is_unchanged() -> None:
    assert "#" not in _iso_row(_att()).evidence_ref


# --- NIST AI RMF -------------------------------------------------------------

NIST = "NIST_AI_RMF:MANAGE 2.1"  # no EU AI Act mapping, so it takes an attestation


def _nist_gap_report() -> GapReport:
    return GapReport(
        system_id="s", commit_ref="c", generated_at="2026-11-03T00:00:00Z", articles=[]
    )


def _nist_sub(report, subcategory: str = "MANAGE 2.1"):
    return next(r for r in report.subcategories if r.subcategory == subcategory)


def test_nist_attestation_expires_like_any_other() -> None:
    live = build_nist_rmf_report(
        _nist_gap_report(), {NIST: _att(valid_until=TODAY)}, TODAY
    )
    dead = build_nist_rmf_report(
        _nist_gap_report(), {NIST: _att(valid_until=date(2026, 11, 2))}, TODAY
    )
    assert _nist_sub(live).status is GapStatus.MET
    row = _nist_sub(dead)
    assert row.status is GapStatus.UNVERIFIED
    assert row.confidence_label is ConfidenceLabel.NOT_ASSESSED
    assert row.rationale == (
        "Attestation expired on 2026-11-02. Renew it under "
        "framework_inputs.NIST_AI_RMF.attested in the manifest."
    )


def test_nist_gap_view_keeps_the_attestation_reference_when_expired() -> None:
    att = _att(record_id="rec_9", valid_until=date(2026, 1, 1))
    report = nist_rmf_as_gap_report(_nist_gap_report(), {NIST: att}, TODAY)
    row = next(r for r in report.articles if r.article == NIST)
    assert row.status is GapStatus.UNVERIFIED
    assert row.source is ArticleGapSource.ATTESTATION
    assert row.evidence_ref == "attestation:Jane Doe@2026-06-01#rec_9"


def test_nist_gap_view_appends_the_record_id() -> None:
    report = nist_rmf_as_gap_report(
        _nist_gap_report(), {NIST: _att(record_id="rec_9")}, TODAY
    )
    row = next(r for r in report.articles if r.article == NIST)
    assert row.status is GapStatus.MET
    assert row.evidence_ref == "attestation:Jane Doe@2026-06-01#rec_9"


def test_nist_attestation_through_evaluate_targets_honours_today() -> None:
    manifest = SystemManifest(
        system_id="sys",
        intended_purpose="x",
        framework_inputs={
            "NIST_AI_RMF": FrameworkInputs(
                attested={NIST: _att(valid_until=date(2026, 11, 2))}
            )
        },
    )
    for today, status in (
        (date(2026, 11, 2), GapStatus.MET),
        (TODAY, GapStatus.UNVERIFIED),
    ):
        reports = evaluate_targets(
            manifest, ["NIST_AI_RMF"], commit_ref="abc", today=today
        )
        row = next(
            r for r in reports["NIST_AI_RMF"].report.articles if r.article == NIST
        )
        assert row.status is status


# --- the new fields on the model ----------------------------------------------


def test_an_attestation_without_new_fields_serialises_as_before() -> None:
    assert _att().model_dump() == {
        "statement": "Training is run every year and completion is recorded.",
        "attested_by": "Jane Doe",
        "attested_at": "2026-06-01",
    }


def test_the_new_fields_round_trip() -> None:
    att = _att(
        valid_until="2027-01-31",
        record_id="rec_01",
        evidence=[
            {"kind": "link", "ref": "https://wiki.example/training"},
            {"kind": "file", "ref": "training.pdf", "sha256": SHA},
        ],
    )
    assert att.valid_until == date(2027, 1, 31)
    dumped = att.model_dump(mode="json")
    assert dumped["valid_until"] == "2027-01-31"
    assert dumped["evidence"][0] == {
        "kind": "link",
        "ref": "https://wiki.example/training",
    }
    assert Attestation.model_validate(dumped) == att


@pytest.mark.parametrize(
    "over",
    [
        {"evidence": [{"kind": "page", "ref": "x"}]},
        {"evidence": [{"kind": "link", "ref": ""}]},
        {"evidence": [{"kind": "file", "ref": "x", "sha256": "ABC"}]},
        {"evidence": [{"kind": "link", "ref": "x", "note": "extra"}]},
        {"record_id": "has space"},
        {"record_id": "x#y"},
        {"valid_until": "next year"},
        {"unexpected": 1},
    ],
)
def test_bad_values_are_rejected(over: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _att(**over)


def test_a_manifest_attestation_validates_unchanged() -> None:
    raw = {"statement": "s", "attested_by": "b", "attested_at": "2026-01-01"}
    assert Attestation.model_validate(raw).model_dump() == raw


# --- the staleness warning ---------------------------------------------------

REQUIREMENTS = {
    ROW: {"default_ttl_days": 365},
    f"{ISO}:A.6.4": {"default_ttl_days": 90},
    f"{ISO}:A.6.5": {"default_ttl_days": None},
}


def test_attestation_older_than_the_ttl_warns() -> None:
    warnings = stale_attestation_warnings(
        {ROW: _att(attested_at="2025-11-01")}, REQUIREMENTS, TODAY
    )
    assert warnings == [
        f"{ROW}: attested on 2025-11-01, more than 365 days ago. "
        "Re-attest it, or set valid_until on the attestation."
    ]


def test_a_bundle_record_older_than_the_ttl_says_to_re_attest_the_record() -> None:
    warnings = stale_attestation_warnings(
        {ROW: _att(attested_at="2025-11-01", record_id="rec-1")}, REQUIREMENTS, TODAY
    )
    assert warnings == [
        f"{ROW}: attested on 2025-11-01, more than 365 days ago. Re-attest the record."
    ]


def test_the_ttl_day_itself_does_not_warn() -> None:
    on_the_day = TODAY - timedelta(days=365)
    assert not stale_attestation_warnings(
        {ROW: _att(attested_at=on_the_day.isoformat())}, REQUIREMENTS, TODAY
    )
    assert stale_attestation_warnings(
        {ROW: _att(attested_at=(on_the_day - timedelta(days=1)).isoformat())},
        REQUIREMENTS,
        TODAY,
    )


def test_a_timestamp_uses_its_date_prefix_and_each_row_its_own_ttl() -> None:
    warnings = stale_attestation_warnings(
        {f"{ISO}:A.6.4": _att(attested_at="2026-06-01T09:30:00+00:00")},
        REQUIREMENTS,
        TODAY,
    )
    assert len(warnings) == 1
    assert "more than 90 days" in warnings[0]


def test_valid_until_unparseable_dates_unknown_rows_and_no_ttl_are_ignored() -> None:
    attestations = {
        ROW: _att(attested_at="2019-01-01", valid_until=date(2030, 1, 1)),
        f"{ISO}:A.6.4": _att(attested_at="last spring"),
        f"{ISO}:A.6.5": _att(attested_at="2019-01-01"),
        f"{ISO}:A.9.9": _att(attested_at="2019-01-01"),
    }
    assert stale_attestation_warnings(attestations, REQUIREMENTS, TODAY) == []


def test_warnings_are_sorted_by_requirement_id() -> None:
    attestations = {
        f"{ISO}:A.6.4": _att(attested_at="2019-01-01"),
        ROW: _att(attested_at="2019-01-01"),
    }
    warnings = stale_attestation_warnings(attestations, REQUIREMENTS, TODAY)
    assert [w.split(":")[1].split(" ")[0] for w in warnings] == ["A.6.3", "A.6.4"]
