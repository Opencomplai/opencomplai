"""The `crosswalk` source kind and the NIST AI RMF requirements file.

With a crosswalk mapping built from `nist_rmf_as_gap_report`, the native path
over `packs/NIST_AI_RMF/requirements.json` reproduces today's NIST rows.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    Attestation,
    GapReport,
    GapStatus,
)
from opencomplai_core.nist_rmf_report import (
    attestable_subcategories,
    nist_rmf_as_gap_report,
)
from opencomplai_core.pack_registry import PACKS_DIR

REQUIREMENTS = json.loads(
    (PACKS_DIR / "NIST_AI_RMF" / "requirements.json").read_text(encoding="utf-8")
)
TODAY = date(2026, 11, 11)
ATTESTED = "NIST_AI_RMF:MANAGE 2.1"
EU_DECIDED = "NIST_AI_RMF:MANAGE 1.3"


def _attestation(attested_at: str, valid_until: date | None = None) -> Attestation:
    return Attestation(
        valid_until=valid_until,
        statement="Resourcing and non-AI alternatives are reviewed each quarter.",
        attested_by="cto@example.com",
        attested_at=attested_at,
    )


def _eu_row(article: str, status: GapStatus, **extra) -> ArticleGapStatus:
    return ArticleGapStatus(
        article=article,
        status=status,
        source=extra.pop("source", ArticleGapSource.RULE),
        evidence_ref=extra.pop("evidence_ref", f"ref-{article}"),
        **extra,
    )


def _eu_report(rows: list[ArticleGapStatus]) -> GapReport:
    return GapReport(
        system_id="s",
        commit_ref="HEAD",
        generated_at="2026-11-11T00:00:00Z",
        articles=rows,
    )


_EU_SETS = {
    "empty": [],
    "mixed": [
        _eu_row("Art. 9", GapStatus.MET),
        _eu_row("Art. 10", GapStatus.MET),
        _eu_row("Art. 11", GapStatus.PARTIAL),
        _eu_row("Art. 15", GapStatus.MISSING, source=ArticleGapSource.EVALUATOR),
        _eu_row("Art. 17", GapStatus.MISSING),
    ],
    "article_9_missing": [_eu_row("Art. 9", GapStatus.MISSING)],
}
_ATTESTATIONS = {
    "none": {},
    "valid": {
        ATTESTED: _attestation("2026-11-02"),
        EU_DECIDED: _attestation("2026-11-02"),
    },
    "expired": {
        ATTESTED: _attestation("2020-01-01", date(2021, 1, 1)),
        EU_DECIDED: _attestation("2020-01-01", date(2021, 1, 1)),
    },
}


def _both(eu_rows, attestations):
    eu = _eu_report(eu_rows)
    today_view = nist_rmf_as_gap_report(eu, attestations, TODAY)
    mapping = {row.article: row for row in today_view.articles}
    native = build_gap_report(
        "s",
        "HEAD",
        requirements=REQUIREMENTS,
        crosswalk=mapping,
        attestations=attestations,
        today=TODAY,
    )
    return today_view, native


def test_requirements_cover_the_taxonomy_in_order():
    view = nist_rmf_as_gap_report(_eu_report([]), None, TODAY)
    assert list(REQUIREMENTS) == [row.article for row in view.articles]
    assert len(REQUIREMENTS) == 72


def test_attestation_sources_are_exactly_the_attestable_rows():
    with_attestation = {
        rid
        for rid, row in REQUIREMENTS.items()
        if any(s["kind"] == "attestation" for s in row["sources"])
    }
    assert with_attestation == attestable_subcategories()
    # Hybrid rows may lead with an artifact source, but each still carries its own
    # crosswalk source.
    for rid, row in REQUIREMENTS.items():
        assert {"kind": "crosswalk", "ref": rid} in row["sources"]


# Rows still decided by the EU projection alone (crosswalk and attestation sources);
# a row with an artifact or evaluator source is decided by more than the projection.
PROJECTION_ONLY = {
    rid
    for rid, row in REQUIREMENTS.items()
    if {s["kind"] for s in row["sources"]} <= {"crosswalk", "attestation"}
}


@pytest.mark.parametrize("attestation_set", sorted(_ATTESTATIONS))
@pytest.mark.parametrize("eu_set", sorted(_EU_SETS))
def test_native_rows_equal_the_projection(eu_set, attestation_set):
    expected, native = _both(_EU_SETS[eu_set], _ATTESTATIONS[attestation_set])
    assert [r.article for r in native.articles] == [
        r.article for r in expected.articles
    ]
    assert PROJECTION_ONLY
    for want, got in zip(expected.articles, native.articles, strict=True):
        if want.article not in PROJECTION_ONLY:
            continue
        assert (got.status, got.source, got.evidence_ref, got.rationale) == (
            want.status,
            want.source,
            want.evidence_ref,
            want.rationale,
        ), want.article


def test_scenarios_exercise_attested_and_expired_rows():
    _, valid = _both(_EU_SETS["empty"], _ATTESTATIONS["valid"])
    row = next(r for r in valid.articles if r.article == ATTESTED)
    assert (row.status, row.source) == (GapStatus.MET, ArticleGapSource.ATTESTATION)
    _, expired = _both(_EU_SETS["empty"], _ATTESTATIONS["expired"])
    row = next(r for r in expired.articles if r.article == ATTESTED)
    assert (row.status, row.source) == (
        GapStatus.UNVERIFIED,
        ArticleGapSource.ATTESTATION,
    )


def test_without_the_mapping_a_crosswalk_row_is_unverified():
    report = build_gap_report("s", "HEAD", requirements=REQUIREMENTS, today=TODAY)
    for row in report.articles:
        assert row.status == GapStatus.UNVERIFIED
    unmapped = next(r for r in report.articles if r.article == "NIST_AI_RMF:GOVERN 1.1")
    assert unmapped.source == ArticleGapSource.CROSSWALK
    assert unmapped.evidence_ref == "none"


def test_a_ref_missing_from_the_mapping_gives_no_candidate():
    requirements = {
        "X:1": {"sources": [{"kind": "crosswalk", "ref": "X:other"}]},
    }
    report = build_gap_report("s", "HEAD", requirements=requirements, crosswalk={})
    assert report.articles[0].status == GapStatus.UNVERIFIED
    assert report.articles[0].source == ArticleGapSource.CROSSWALK
