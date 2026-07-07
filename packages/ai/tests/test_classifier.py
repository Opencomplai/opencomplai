"""Tests for opencomplai_ai.classifier (deterministic code_signals matcher)."""

from unittest.mock import patch

import pytest
from opencomplai_ai.classifier import (
    IntentClassifier,
    _match_annex_iii,
    _match_prohibited,
)
from opencomplai_ai.models import IntentAnnotation


@pytest.fixture
def classifier(tmp_path):
    fake_model = tmp_path / "codebert-base-onnx.tar.gz"
    fake_model.write_bytes(b"fake")
    with patch(
        "opencomplai_ai.classifier.IntentClassifier.__init__", lambda self: None
    ):
        clf = IntentClassifier.__new__(IntentClassifier)
        clf._model_path = fake_model
        clf._session = None
        clf._tokenizer = None
        return clf


def test_classify_returns_intent_annotation(classifier):
    result = classifier.classify("credit_score = model.predict(user_data)")
    assert isinstance(result, IntentAnnotation)
    assert result.model_id == "codebert-onnx"
    assert 0.0 <= result.confidence <= 1.0
    assert result.decision_autonomy in (
        "autonomous",
        "advisory",
        "human_in_loop",
        "display_only",
        "unknown",
    )


def test_classify_credit_scoring_resolves_area_5(classifier):
    result = classifier.classify("risk_score = scorecard.predict(applicant)")
    assert result.annex_iii_area == 5
    assert result.art6_3_profiling is True
    assert any("Art.6(2)" in o for o in result.eu_obligation)


def test_classify_facial_recognition_resolves_area_1(classifier):
    result = classifier.classify("embedding = face_recognition.encode(img)")
    assert result.annex_iii_area == 1
    assert result.eu_obligation  # must cite actual articles, not generic fallback


def test_classify_prohibited_workplace_emotion(classifier):
    result = classifier.classify("score = employee_emotion.detect(frame)")
    assert result.art5_prohibited is True


def test_classify_unknown_snippet_returns_none(classifier):
    result = classifier.classify("x = 1 + 2")
    assert result is None


def test_classify_unknown_snippet_legacy_returns_minimal(classifier):
    result = classifier.classify("x = 1 + 2", legacy=True)
    assert isinstance(result, IntentAnnotation)
    assert result.model_id == "codebert-onnx"
    assert result.annex_iii_area is None
    assert result.decision_autonomy == "display_only"
    assert result.confidence == 0.5


def test_classify_label_validity(classifier):
    result = classifier.classify("risk_score = scorecard.predict(applicant)")
    assert result is not None
    assert result.decision_autonomy in (
        "autonomous",
        "advisory",
        "human_in_loop",
        "display_only",
        "unknown",
    )
    assert result.subject_type in (
        "natural_person",
        "legal_entity",
        "system",
        "unknown",
    )
    assert result.consequential in ("yes", "no", "unknown")


def test_match_annex_iii_credit_signal():
    match = _match_annex_iii("predict_default(applicant_id)")
    assert match is not None
    assert match.area == 5
    assert match.art6_3 is True


def test_match_annex_iii_no_signal():
    match = _match_annex_iii("print('hello world')")
    assert match is None


def test_match_annex_iii_transfer_speed_column_not_emotion():
    match = _match_annex_iii("", token="TransferSpeedColumn")
    assert match is None


def test_match_annex_iii_explicit_fer_is_emotion():
    match = _match_annex_iii("result = fer.analyze(frame)", token="fer")
    assert match is not None
    assert match.area == 1
    assert "fer" in match.matched_signals


def test_match_prohibited_social_scoring():
    match = _match_prohibited("citizen_score = trust_model.score(user)")
    assert match is not None


def test_match_prohibited_clean_code():
    match = _match_prohibited("result = calculator.add(1, 2)")
    assert match is None


def test_classify_credit_scoring_applicant_stays_high_risk(classifier):
    """Natural-person cue ('applicant') present alongside credit signal."""
    result = classifier.classify("risk_score = scorecard.predict(applicant)")
    assert result.annex_iii_area == 5
    assert result.risk_tier == "high_risk"
    assert result.subject_type == "natural_person"


def test_classify_portfolio_credit_scoring_is_not_high_risk(classifier):
    """Product/entity cue ('portfolio'), no person cue -> not Annex III."""
    result = classifier.classify(
        "risk_score = scorecard.predict(bond_portfolio)", token="predict_default"
    )
    assert result is not None
    assert result.annex_iii_area is None
    assert result.risk_tier != "high_risk"
    assert result.subject_type in ("legal_entity", "system")


def test_classify_counterparty_default_prediction_is_not_high_risk(classifier):
    result = classifier.classify("predict_default(counterparty_id)")
    assert result is not None
    assert result.annex_iii_area is None
    assert result.subject_type in ("legal_entity", "system")


def test_classify_vendor_scorecard_is_not_high_risk(classifier):
    result = classifier.classify("scorecard.predict(vendor_id)")
    assert result is not None
    assert result.annex_iii_area is None


def test_classify_biometric_area_ignores_product_cue(classifier):
    """Area 1 is not subject_gated; a product cue elsewhere must not suppress it."""
    result = classifier.classify(
        "embedding = face_recognition.encode(product_photo)"
    )
    assert result.annex_iii_area == 1


def test_classify_gemini_rest_route_is_limited_risk(classifier):
    snippet = (
        "const apiKey = process.env.GEMINI_API_KEY;\n"
        "await fetch('https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent?key=' + apiKey);"
    )
    result = classifier.classify(snippet, token="gemini_api")
    assert result is not None
    assert result.risk_tier == "limited_risk"
    assert result.explanation
    assert result.needed_action
