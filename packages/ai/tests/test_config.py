"""Tests for opencomplai_ai.config."""

from pathlib import Path
from unittest.mock import patch

import pytest

from opencomplai_ai.config import get_active_model, set_active_model
from opencomplai_ai.models import MODEL_CATALOG


def test_get_active_model_default(tmp_path):
    with patch("opencomplai_ai.config._AI_CONFIG_FILE", tmp_path / "ai-config.yaml"):
        assert get_active_model() == "qwen2.5-coder-1.5b"


def test_get_active_model_reads_file(tmp_path):
    cfg = tmp_path / "ai-config.yaml"
    cfg.write_text("model_id: codebert-onnx\n", encoding="utf-8")
    with patch("opencomplai_ai.config._AI_CONFIG_FILE", cfg):
        assert get_active_model() == "codebert-onnx"


def test_get_active_model_unknown_falls_back(tmp_path):
    cfg = tmp_path / "ai-config.yaml"
    cfg.write_text("model_id: nonexistent-model\n", encoding="utf-8")
    with patch("opencomplai_ai.config._AI_CONFIG_FILE", cfg):
        assert get_active_model() == "qwen2.5-coder-1.5b"


def test_set_active_model_writes_file(tmp_path):
    cfg = tmp_path / "ai-config.yaml"
    with (
        patch("opencomplai_ai.config._AI_CONFIG_FILE", cfg),
        patch("opencomplai_ai.config._CONFIG_DIR", tmp_path),
    ):
        set_active_model("codebert-onnx")
        assert cfg.exists()
        with patch("opencomplai_ai.config._AI_CONFIG_FILE", cfg):
            assert get_active_model() == "codebert-onnx"


def test_set_active_model_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown model"):
        set_active_model("does-not-exist")


def test_all_catalog_ids_are_settable(tmp_path):
    for model_id in MODEL_CATALOG:
        cfg = tmp_path / f"ai-config-{model_id.replace('.', '_')}.yaml"
        with (
            patch("opencomplai_ai.config._AI_CONFIG_FILE", cfg),
            patch("opencomplai_ai.config._CONFIG_DIR", tmp_path),
        ):
            set_active_model(model_id)
            with patch("opencomplai_ai.config._AI_CONFIG_FILE", cfg):
                assert get_active_model() == model_id
