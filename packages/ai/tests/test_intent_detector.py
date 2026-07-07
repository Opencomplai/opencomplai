"""Tests for opencomplai_ai.detector (mocked registry)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from opencomplai_ai.detector import IntentDetector
from opencomplai_ai.models import IntentAnnotation
from opencomplai_core.models import EvidenceItem, EvidenceScope
from opencomplai_core.scanner.feature_types import CallsiteRef, FeatureStore, ImportRef


def _make_features(tmp_path: Path) -> FeatureStore:
    src = tmp_path / "src.py"
    src.write_text("result = model.predict(data)\n", encoding="utf-8")
    store = FeatureStore(repo_root=tmp_path)
    store.callsites.append(
        CallsiteRef(name="model.predict", location=f"{src}:1", scope=EvidenceScope.PROD)
    )
    store.imports.append(
        ImportRef(
            module="sklearn.linear_model", location=f"{src}:1", scope=EvidenceScope.PROD
        )
    )
    return store


def test_detect_populates_intent_annotation(tmp_path):
    features = _make_features(tmp_path)
    mock_annotation = IntentAnnotation(
        decision_autonomy="autonomous",
        subject_type="natural_person",
        consequential="yes",
        eu_obligation=["Art.6(2)+Annex III"],
        model_id="codebert-onnx",
        confidence=0.85,
    )
    mock_backend = MagicMock()
    mock_backend.classify.return_value = mock_annotation

    with patch("opencomplai_ai.detector.ModelRegistry") as mock_registry:
        mock_registry.resolve.return_value = mock_backend
        detector = IntentDetector("codebert-onnx")
        evidence = detector.detect(features)

    assert len(evidence) > 0
    assert all(isinstance(ev, EvidenceItem) for ev in evidence)
    annotated = [ev for ev in evidence if ev.intent_annotation is not None]
    assert len(annotated) > 0
    ann = annotated[0].intent_annotation
    assert ann.decision_autonomy == "autonomous"
    assert ann.confidence == 0.85


def test_detect_detector_id():
    detector = IntentDetector("codebert-onnx")
    assert detector.detector_id == "DET_INTENT_V1"
    assert detector.detector_version == "1.1.0"


def test_detect_empty_features(tmp_path):
    features = FeatureStore(repo_root=tmp_path)
    mock_backend = MagicMock()
    mock_backend.classify.return_value = IntentAnnotation(model_id="codebert-onnx")

    with patch("opencomplai_ai.detector.ModelRegistry") as mock_registry:
        mock_registry.resolve.return_value = mock_backend
        detector = IntentDetector("codebert-onnx")
        evidence = detector.detect(features)

    assert evidence == []


def test_detect_graceful_on_classify_error(tmp_path):
    features = _make_features(tmp_path)
    mock_backend = MagicMock()
    mock_backend.classify.side_effect = RuntimeError("model crashed")

    with patch("opencomplai_ai.detector.ModelRegistry") as mock_registry:
        mock_registry.resolve.return_value = mock_backend
        detector = IntentDetector("codebert-onnx")
        with pytest.raises(RuntimeError):
            detector.detect(features)
