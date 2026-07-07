"""Tests for opencomplai_ai.explainer JSON parsing."""

from __future__ import annotations

import pytest
from opencomplai_ai.explainer import _parse_annotation
from opencomplai_ai.models import IntentAnnotation


def test_parse_annotation_credit_scoring_area_5():
    data = {
        "annex_iii_area": 5,
        "art5_prohibited": False,
        "art6_3_profiling": True,
        "decision_autonomy": "autonomous",
        "subject_type": "natural_person",
        "consequential": "yes",
        "explanation": "Credit scoring under Annex III area 5(b).",
    }
    ann = _parse_annotation(data, model_id="qwen2.5-coder", confidence=0.92)
    assert isinstance(ann, IntentAnnotation)
    assert ann.annex_iii_area == 5
    assert ann.art6_3_profiling is True
    assert ann.art5_prohibited is False
    assert ann.decision_autonomy == "autonomous"
    assert any("Art." in o for o in ann.eu_obligation)


def test_parse_annotation_rejects_invalid_area():
    data = {
        "annex_iii_area": 99,
        "art5_prohibited": False,
        "art6_3_profiling": False,
        "decision_autonomy": "display_only",
        "subject_type": "system",
        "consequential": "no",
        "explanation": "No Annex III match.",
    }
    ann = _parse_annotation(data, model_id="qwen2.5-coder", confidence=0.5)
    assert ann.annex_iii_area is None


def test_parse_annotation_art5_prohibited():
    data = {
        "annex_iii_area": None,
        "art5_prohibited": True,
        "art6_3_profiling": False,
        "decision_autonomy": "autonomous",
        "subject_type": "natural_person",
        "consequential": "yes",
        "explanation": "Social scoring prohibited under Art. 5.",
    }
    ann = _parse_annotation(data, model_id="qwen2.5-coder", confidence=0.95)
    assert ann.art5_prohibited is True


@pytest.mark.parametrize("bad_area", [3.5, "five", None])
def test_parse_annotation_coerces_non_integer_area(bad_area):
    data = {
        "annex_iii_area": bad_area,
        "art5_prohibited": False,
        "art6_3_profiling": False,
        "decision_autonomy": "unknown",
        "subject_type": "unknown",
        "consequential": "unknown",
        "explanation": "",
    }
    ann = _parse_annotation(data, model_id="test", confidence=0.1)
    if bad_area == 3.5:
        assert ann.annex_iii_area is None
    else:
        assert ann.annex_iii_area is None
