"""Tests for opencomplai_ai.registry."""

from unittest.mock import MagicMock, patch

import pytest
from opencomplai_ai.models import MODEL_CATALOG
from opencomplai_ai.registry import ModelNotInstalledError, ModelRegistry


def setup_function():
    ModelRegistry.clear_cache()


def teardown_function():
    ModelRegistry.clear_cache()


def test_resolve_codebert_returns_classifier():
    from opencomplai_ai.classifier import IntentClassifier

    mock_classifier = MagicMock(spec=IntentClassifier)
    with patch(
        "opencomplai_ai.registry.IntentClassifier", return_value=mock_classifier
    ):
        backend = ModelRegistry.resolve("codebert-onnx")
    assert backend is mock_classifier


def test_resolve_saas_returns_saas_client():
    from opencomplai_ai._saas_client import SaaSIntentClient

    mock_client = MagicMock(spec=SaaSIntentClient)
    with patch("opencomplai_ai.registry.SaaSIntentClient", return_value=mock_client):
        backend = ModelRegistry.resolve("saas")
    assert backend is mock_client


def test_resolve_gguf_model_returns_explainer():
    from opencomplai_ai.explainer import IntentExplainer

    mock_explainer = MagicMock(spec=IntentExplainer)
    with (
        patch("opencomplai_ai.registry.IntentExplainer", return_value=mock_explainer),
        patch.dict("sys.modules", {"llama_cpp": MagicMock()}),
    ):
        backend = ModelRegistry.resolve("qwen2.5-coder-1.5b")
    assert backend is mock_explainer


def test_resolve_unknown_raises():
    with pytest.raises(ValueError, match="Unknown model"):
        ModelRegistry.resolve("not-a-real-model")


def test_resolve_deep_model_missing_llama_cpp():
    with patch.dict("sys.modules", {"llama_cpp": None}):
        with pytest.raises(ModelNotInstalledError, match="llama-cpp-python"):
            ModelRegistry.resolve("mistral-7b")


def test_all_non_deep_models_resolve_without_llama_cpp():
    non_deep = [mid for mid, spec in MODEL_CATALOG.items() if not spec.requires_deep]
    for model_id in non_deep:
        ModelRegistry.clear_cache()
        mock_backend = MagicMock()
        patch_target = {
            "codebert-onnx": "opencomplai_ai.registry.IntentClassifier",
            "saas": "opencomplai_ai.registry.SaaSIntentClient",
        }[model_id]
        with patch(patch_target, return_value=mock_backend):
            backend = ModelRegistry.resolve(model_id)
        assert backend is mock_backend


def test_resolve_caches_instance():
    mock_backend = MagicMock()
    with patch("opencomplai_ai.registry.IntentClassifier", return_value=mock_backend):
        b1 = ModelRegistry.resolve("codebert-onnx")
        b2 = ModelRegistry.resolve("codebert-onnx")
    assert b1 is b2
