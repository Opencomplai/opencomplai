"""The eleven further native packs (ISO 27001, SOC 2, NIS2, DORA, EBA, EIOPA, GDPR, CRA,
ETSI EN 304 223, ISO 42005, ISO 23894): attestation-led, flagged data, links that resolve.

Shape checks every pack shares (prefix, titles, TTLs, source kinds) live in
test_framework_packs.py; this file pins what is specific to these packs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.frameworks import (
    FRAMEWORKS,
    evaluate_targets,
    gate_failures,
    load_requirements_map,
)
from opencomplai_core.models import (
    Attestation,
    ConfidenceLabel,
    FrameworkInputs,
    GapStatus,
    SystemManifest,
)

ROWS = {
    "ISO_IEC_27001": 118,
    "SOC_2": 61,
    "NIS2": 21,
    "DORA": 37,
    "EBA": 25,
    "EIOPA_AI": 8,
    "GDPR": 21,
    "CRA": 63,
    "ETSI_EN_304_223": 72,
    "ISO_IEC_42005": 20,
    "ISO_IEC_23894": 23,
}
DATA = Path(FRAMEWORKS["EU_AI_ACT"].requirements).parent
EU_ARTICLES = {
    k
    for k in json.loads((DATA / "gap_article_map.json").read_text("utf-8"))
    if not k.startswith("_")
}


def _rows(key: str) -> dict[str, dict]:
    return load_requirements_map(FRAMEWORKS[key].requirements)


def _report(key: str, attested: tuple[str, ...] = ()):
    attestation = Attestation(
        statement="Covered by our programme.",
        attested_by="ciso@example.com",
        attested_at="2026-11-03",
    )
    inputs = {key: FrameworkInputs(attested=dict.fromkeys(attested, attestation))}
    manifest = SystemManifest(
        system_id="sys", intended_purpose="support chatbot", framework_inputs=inputs
    )
    return evaluate_targets(manifest, [key], commit_ref="HEAD")


@pytest.mark.parametrize("key", ROWS)
def test_rows_are_flagged_and_links_resolve(key: str):
    rows = _rows(key)
    assert len(rows) == ROWS[key]
    iso27001 = {rid.split(":", 1)[1] for rid in _rows("ISO_IEC_27001")}
    iso42001 = set(_rows("ISO_IEC_42001"))
    for rid, row in rows.items():
        assert 0 < len(row["title"]) <= 80, rid
        assert row["note"].strip(), rid
        assert "\n" not in row["note"], rid
        assert row["confidence"] == "low", rid
        assert row["needs_founder_review"] is True, rid
        assert row["sources"][0] == {"kind": "attestation", "ref": rid}, rid
        assert set(row["eu_ai_act"]) <= EU_ARTICLES, rid
        assert set(row.get("iso_27001", [])) <= iso27001, rid
        assert set(row.get("iso_42001", [])) <= iso42001, rid
    if key == "ISO_IEC_27001":
        assert not any("iso_27001" in row for row in rows.values())


@pytest.mark.parametrize("key", ROWS)
def test_unattested_rows_are_unverified_and_never_fail_a_gate(key: str):
    reports = _report(key)
    rows = reports[key].report.articles
    assert len(rows) == ROWS[key]
    assert {r.status for r in rows} == {GapStatus.UNVERIFIED}
    assert gate_failures(reports, [key], "partial") == []


@pytest.mark.parametrize("key", ROWS)
def test_an_attestation_makes_a_row_met(key: str):
    rid = next(iter(_rows(key)))
    row = {r.article: r for r in _report(key, (rid,))[key].report.articles}[rid]
    assert row.status == GapStatus.MET
    assert row.confidence_label == ConfidenceLabel.ATTESTED


def test_iso_27090_anchors_are_rows_of_the_27001_and_soc_2_packs():
    iso27001 = {rid.split(":", 1)[1] for rid in _rows("ISO_IEC_27001")}
    soc2 = {rid.split(":", 1)[1] for rid in _rows("SOC_2")}
    for rid, row in _rows("ISO_IEC_27090").items():
        assert set(row["iso_27001"]) <= iso27001, rid
        assert set(row["soc2"]) <= soc2, rid
