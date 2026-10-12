"""Aggregation of call-site findings into one unconfirmed classification proposal."""

from __future__ import annotations

import random

import pytest
from opencomplai_core.models import (
    EuAiRegulatoryFinding,
    EuAiScanSummary,
    FlagRationale,
)
from opencomplai_core.scanner.proposal import (
    CONFIDENCE_BASIS,
    CONFIDENCE_LABEL_BANDS,
    build_classification_proposal,
)


def _finding(
    location: str,
    area: int | None,
    *,
    function: str = "fn",
    tier: str = "high_risk",
    signals: list[str] | None = None,
    declared: bool = False,
    rationale: bool = True,
) -> EuAiRegulatoryFinding:
    return EuAiRegulatoryFinding(
        location=location,
        function=function,
        risk_tier=tier,
        annex_iii_area=area,
        rationale=(
            FlagRationale(
                summary="s",
                matched_signals=signals or ["sig"],
                regulation_ref=f"Annex III area {area}",
                knowledge_entry_title=f"entry {area}",
                declared_purpose_used=declared,
            )
            if rationale
            else None
        ),
    )


def _summary(
    high: list | None = None,
    prohibited: list | None = None,
    limited: list | None = None,
) -> EuAiScanSummary:
    return EuAiScanSummary(
        high_risk=high or [],
        prohibited=prohibited or [],
        limited_risk=limited or [],
    )


def test_three_employment_one_stray_biometric_proposes_employment():
    summary = _summary(
        high=[
            _finding("hr/a.py:10", 4, function="rank_candidates"),
            _finding("hr/b.py:20", 4, function="screen_resume"),
            _finding("hr/c.py:30", 4, function="score_candidate"),
            _finding("misc/d.py:5", 1, function="predict_ethnicity"),
            # Higher area number and sorts before the employment lines, so a
            # max-area or first-by-order winner rule cannot pass this test.
            _finding("a_stray.py:5", 5, function="credit_score"),
        ]
    )
    proposal = build_classification_proposal(summary)
    assert proposal.proposed_annex_iii_area == 4
    assert proposal.proposed_area_name == "employment"
    assert proposal.supporting_count == 3
    assert [ln.location for ln in proposal.supporting_evidence] == [
        "hr/a.py:10",
        "hr/b.py:20",
        "hr/c.py:30",
    ]
    assert [(ln.location, ln.annex_iii_area) for ln in proposal.minority_evidence] == [
        ("a_stray.py:5", 5),
        ("misc/d.py:5", 1),
    ]
    assert proposal.confidence_label == "medium"
    assert proposal.tie_areas == []


def test_empty_summary_proposes_none():
    proposal = build_classification_proposal(_summary())
    assert proposal.proposed_annex_iii_area is None
    assert proposal.proposed_area_name is None
    assert proposal.confidence_label == "none"
    assert proposal.supporting_count == 0
    assert proposal.supporting_evidence == []
    assert proposal.minority_evidence == []


def test_no_summary_proposes_none():
    proposal = build_classification_proposal(None)
    assert proposal.proposed_annex_iii_area is None
    assert proposal.confidence_label == "none"
    assert proposal.supporting_count == 0
    assert proposal.confirmation_status == "unconfirmed"


def test_prohibited_signals_listed_not_counted_toward_area():
    summary = _summary(
        high=[_finding("a.py:1", 4), _finding("b.py:2", 4)],
        prohibited=[
            _finding(
                "z/emotion.py:9", None, function="detect_emotion", tier="prohibited"
            ),
            _finding("y/scrape.py:3", None, function="scrape_faces", tier="prohibited"),
        ],
    )
    proposal = build_classification_proposal(summary)
    assert proposal.proposed_annex_iii_area == 4
    assert proposal.supporting_count == 2
    assert [(ln.file, ln.line) for ln in proposal.prohibited_signals] == [
        ("y/scrape.py", 3),
        ("z/emotion.py", 9),
    ]
    assert all(ln.annex_iii_area is None for ln in proposal.prohibited_signals)
    assert proposal.minority_evidence == []

    only_prohibited = build_classification_proposal(
        _summary(prohibited=[_finding("p.py:1", None, tier="prohibited")])
    )
    assert only_prohibited.proposed_annex_iii_area is None
    assert only_prohibited.supporting_count == 0
    assert len(only_prohibited.prohibited_signals) == 1


def test_evidence_lines_carry_file_and_line():
    summary = _summary(
        high=[
            _finding("src/app/hr.py:42", 4, function="rank", signals=["rank_x"]),
            _finding("src/app/noline.py", 4, function="score", rationale=False),
            _finding("src/app/bad.py:abc", 4, function="pick"),
        ]
    )
    proposal = build_classification_proposal(summary)
    by_loc = {ln.location: ln for ln in proposal.supporting_evidence}

    hr = by_loc["src/app/hr.py:42"]
    assert (hr.file, hr.line) == ("src/app/hr.py", 42)
    assert hr.function == "rank"
    assert hr.signals == ["rank_x"]
    assert hr.entry_title == "entry 4"
    assert hr.regulation_ref == "Annex III area 4"
    assert hr.risk_tier == "high_risk"

    noline = by_loc["src/app/noline.py"]
    assert (noline.file, noline.line) == ("src/app/noline.py", None)
    assert noline.signals == []
    assert noline.entry_title is None
    assert noline.regulation_ref == ""

    bad = by_loc["src/app/bad.py:abc"]
    assert (bad.file, bad.line) == ("src/app/bad.py:abc", None)


@pytest.mark.parametrize(
    ("n", "label"),
    [(0, "none"), (1, "low"), (2, "medium"), (3, "medium"), (4, "high"), (7, "high")],
)
def test_confidence_label_from_supporting_count(n, label):
    summary = _summary(high=[_finding(f"f{i}.py:1", 4) for i in range(n)])
    proposal = build_classification_proposal(summary)
    assert proposal.supporting_count == n
    assert proposal.confidence_label == label
    assert proposal.confidence_basis == CONFIDENCE_BASIS


def test_confidence_bands_are_documented_as_data():
    assert CONFIDENCE_LABEL_BANDS["source"] == "CL-C2 spec heuristic"
    assert CONFIDENCE_LABEL_BANDS["confidence"] == "low"
    assert CONFIDENCE_LABEL_BANDS["needs_founder_review"] is True
    assert build_classification_proposal(None).needs_founder_review is True


def test_confidence_label_ignores_minority_evidence():
    base = [_finding("a.py:1", 4), _finding("b.py:1", 4)]
    alone = build_classification_proposal(_summary(high=base))
    with_minority = build_classification_proposal(
        _summary(high=[*base, _finding("c.py:1", 2)])
    )
    assert with_minority.minority_evidence
    assert alone.confidence_label == with_minority.confidence_label == "medium"


def test_tie_between_areas_proposes_none():
    summary = _summary(
        high=[
            _finding("a.py:1", 4),
            _finding("b.py:1", 4),
            _finding("c.py:1", 1),
            _finding("d.py:1", 1),
            _finding("e.py:1", 5),
        ]
    )
    proposal = build_classification_proposal(summary)
    assert proposal.proposed_annex_iii_area is None
    assert proposal.proposed_area_name is None
    assert proposal.tie_areas == [1, 4]
    assert proposal.confidence_label == "none"
    assert proposal.supporting_count == 0
    assert proposal.supporting_evidence == []
    assert len(proposal.minority_evidence) == 5
    assert any("equal support" in n for n in proposal.notes)


def test_declared_purpose_echo_not_counted():
    summary = _summary(
        high=[
            _finding("a.py:1", 4),
            _finding("b.py:1", 1, declared=True),
            _finding("c.py:1", 1, declared=True),
        ]
    )
    proposal = build_classification_proposal(summary)
    assert proposal.proposed_annex_iii_area == 4
    assert proposal.supporting_count == 1
    assert [ln.location for ln in proposal.declared_purpose_echo] == [
        "b.py:1",
        "c.py:1",
    ]
    assert proposal.minority_evidence == []

    only_echo = build_classification_proposal(
        _summary(high=[_finding("a.py:1", 4, declared=True)])
    )
    assert only_echo.proposed_annex_iii_area is None
    assert only_echo.confidence_label == "none"
    assert len(only_echo.declared_purpose_echo) == 1


def test_same_location_counted_once():
    summary = _summary(
        high=[
            _finding("a.py:1", 4, function="b_fn"),
            _finding("a.py:1", 4, function="a_fn"),
            _finding("b.py:1", 1),
        ]
    )
    proposal = build_classification_proposal(summary)
    # One call site per area: a tie, not a 2-to-1 win for area 4.
    assert proposal.proposed_annex_iii_area is None
    assert proposal.tie_areas == [1, 4]
    kept = [ln for ln in proposal.minority_evidence if ln.location == "a.py:1"]
    assert [ln.function for ln in kept] == ["a_fn"]


def test_limited_risk_and_area_none_findings_ignored():
    summary = _summary(
        high=[_finding("a.py:1", 4), _finding("n.py:1", None)],
        limited=[
            _finding("l1.py:1", 5, tier="limited_risk"),
            _finding("l2.py:1", 5, tier="limited_risk"),
        ],
    )
    proposal = build_classification_proposal(summary)
    assert proposal.proposed_annex_iii_area == 4
    assert proposal.supporting_count == 1
    assert proposal.minority_evidence == []
    assert proposal.prohibited_signals == []


def test_output_is_deterministic_and_json_round_trips():
    findings = [
        _finding(f"pkg/m{i % 4}.py:{i}", 4 if i % 3 else 1, function=f"f{i}")
        for i in range(12)
    ]
    prohibited = [
        _finding("pro/x.py:2", None, tier="prohibited"),
        _finding("pro/a.py:7", None, tier="prohibited"),
    ]
    first = build_classification_proposal(
        _summary(high=findings, prohibited=prohibited)
    )

    shuffled = list(findings)
    shuffled_pro = list(prohibited)
    rng = random.Random(7)
    rng.shuffle(shuffled)
    rng.shuffle(shuffled_pro)
    second = build_classification_proposal(
        _summary(high=shuffled, prohibited=shuffled_pro)
    )

    assert first.model_dump_json() == second.model_dump_json()
    restored = type(first).model_validate_json(first.model_dump_json())
    assert restored == first


def test_confirmation_status_always_unconfirmed():
    cases = [
        None,
        _summary(),
        _summary(high=[_finding("a.py:1", 4)] * 4),
        _summary(high=[_finding("a.py:1", 4), _finding("b.py:1", 1)]),
        _summary(prohibited=[_finding("p.py:1", None, tier="prohibited")]),
    ]
    for case in cases:
        proposal = build_classification_proposal(case)
        assert proposal.confirmation_status == "unconfirmed"
        assert proposal.needs_founder_review is True
