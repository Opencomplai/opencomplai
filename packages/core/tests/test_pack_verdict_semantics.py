"""Verdict semantics every native pack other than the EU AI Act must keep.

One shared table, parametrised over the registry, so a pack that adds source
kinds, roles or an evidence class cannot change what Met, Missing and
corroborated mean.
"""

from __future__ import annotations

from datetime import date

import pytest
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    FRAMEWORKS,
    attestable_ids,
    pack_requirements,
)
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import (
    ArticleGapSource,
    Attestation,
    GapReport,
    GapStatus,
)

TODAY = date(2026, 11, 11)
EVIDENCE_CLASSES = {"machine", "hybrid", "organisational"}

NATIVE_KEYS = sorted(
    key
    for key, pack in FRAMEWORKS.items()
    if key != EU_AI_ACT and pack.requirements is not None
)


def _attestation() -> Attestation:
    return Attestation(
        statement="Reviewed by the responsible owner.",
        attested_by="owner@example.com",
        attested_at="2026-11-02",
    )


def _report(key: str, *, attest: bool) -> GapReport:
    requirements = pack_requirements(FRAMEWORKS[key])
    assert requirements is not None
    attestations = (
        {rid: _attestation() for rid in attestable_ids(key)} if attest else {}
    )
    return build_gap_report(
        "sys",
        "HEAD",
        requirements=requirements,
        attestations=attestations,
        today=TODAY,
    )


def test_there_are_native_non_eu_packs_to_check():
    assert NATIVE_KEYS


@pytest.mark.parametrize("key", NATIVE_KEYS)
def test_no_attestation_and_no_repo_root_leaves_no_row_met(key: str):
    report = _report(key, attest=False)
    assert report.articles
    assert [r.article for r in report.articles if r.status == GapStatus.MET] == []


@pytest.mark.parametrize("key", NATIVE_KEYS)
def test_every_attestable_row_attested_leaves_no_row_missing(key: str):
    report = _report(key, attest=True)
    assert [r.article for r in report.articles if r.status == GapStatus.MISSING] == []


@pytest.mark.parametrize("attest", [False, True])
@pytest.mark.parametrize("key", NATIVE_KEYS)
def test_corroborated_is_true_only_on_met_attestation_rows(key: str, attest: bool):
    for row in _report(key, attest=attest).articles:
        if row.corroborated is True:
            assert row.status == GapStatus.MET, row.article
            assert row.source == ArticleGapSource.ATTESTATION, row.article


@pytest.mark.parametrize("attest", [False, True])
@pytest.mark.parametrize("key", NATIVE_KEYS)
def test_a_row_carries_the_evidence_class_of_its_pack_data(key: str, attest: bool):
    requirements = pack_requirements(FRAMEWORKS[key])
    assert requirements is not None
    rows = {r.article: r for r in _report(key, attest=attest).articles}
    assert set(rows) == set(requirements)
    for rid, config in requirements.items():
        declared = config.get("evidence_class")
        assert declared is None or declared in EVIDENCE_CLASSES, rid
        assert rows[rid].evidence_class == declared, rid
        assert ("evidence_class" in rows[rid].model_dump(mode="json")) == (
            declared is not None
        ), rid


@pytest.mark.parametrize("key", NATIVE_KEYS)
def test_a_machine_or_hybrid_row_has_a_source_that_can_decide_it(key: str):
    requirements = pack_requirements(FRAMEWORKS[key])
    assert requirements is not None
    for rid, config in requirements.items():
        if config.get("evidence_class") not in {"machine", "hybrid"}:
            continue
        deciding = [
            s
            for s in config["sources"]
            if s["kind"] != "attestation" and s.get("role") != "supporting"
        ]
        assert deciding, f"{rid}: no source other than an attestation or supporting"
