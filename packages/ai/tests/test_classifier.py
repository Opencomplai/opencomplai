"""Tests for opencomplai_ai.classifier (mocked ONNX session)."""

from unittest.mock import MagicMock, patch

import pytest

from opencomplai_ai.classifier import IntentClassifier
from opencomplai_ai.models import IntentAnnotation


def _make_mock_session(embedding_size: int = 768):
    import numpy as np

    session = MagicMock()
    session.run.return_value = [np.ones((1, 10, embedding_size), dtype="float32")]
    return session


def _make_mock_tokenizer():
    import numpy as np

    tokenizer = MagicMock()
    tokenizer.return_value = {
        "input_ids": np.array([[101, 102]]),
        "attention_mask": np.array([[1, 1]]),
    }
    return tokenizer


@pytest.fixture()
def classifier(tmp_path):
    fake_model = tmp_path / "codebert-base-onnx.tar.gz"
    fake_model.write_bytes(b"fake")

    with (
        patch("opencomplai_ai.classifier.IntentClassifier.__init__", lambda self: None),
    ):
        clf = IntentClassifier.__new__(IntentClassifier)
        clf._model_path = fake_model
        clf._session = None
        clf._tokenizer = None
        clf._pattern_embeddings = {}
        return clf


def test_classify_returns_intent_annotation(classifier):
    import numpy as np

    mock_session = MagicMock()
    mock_session.run.return_value = [np.ones((1, 5, 768), dtype="float32")]
    mock_tokenizer = _make_mock_tokenizer()

    with (
        patch("onnxruntime.InferenceSession", return_value=mock_session),
        patch("transformers.AutoTokenizer.from_pretrained", return_value=mock_tokenizer),
    ):
        classifier._session = mock_session
        classifier._tokenizer = mock_tokenizer
        classifier._precompute_pattern_embeddings()
        result = classifier.classify("model.predict(user_data)")

    assert isinstance(result, IntentAnnotation)
    assert result.model_id == "codebert-onnx"
    assert 0.0 <= result.confidence <= 1.0
    assert result.decision_autonomy in ("autonomous", "advisory", "human_in_loop", "display_only", "unknown")


def test_classify_returns_unknown_on_failure(classifier):
    classifier._session = MagicMock(side_effect=RuntimeError("ONNX error"))
    classifier._tokenizer = MagicMock()
    classifier._pattern_embeddings = {}

    result = classifier.classify("some code")
    assert isinstance(result, IntentAnnotation)
    assert result.model_id == "codebert-onnx"
    assert result.confidence == 0.0


def test_classify_label_validity(classifier):
    import numpy as np

    mock_session = MagicMock()
    mock_session.run.return_value = [np.random.rand(1, 5, 768).astype("float32")]
    mock_tokenizer = _make_mock_tokenizer()

    classifier._session = mock_session
    classifier._tokenizer = mock_tokenizer
    classifier._precompute_pattern_embeddings()
    result = classifier.classify("score = model(features)")

    assert result.decision_autonomy in ("autonomous", "advisory", "human_in_loop", "display_only", "unknown")
    assert result.subject_type in ("natural_person", "legal_entity", "system", "unknown")
    assert result.consequential in ("yes", "no", "unknown")
