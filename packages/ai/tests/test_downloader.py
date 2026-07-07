"""Tests for opencomplai_ai.downloader."""

from unittest.mock import MagicMock, patch

import pytest
from opencomplai_ai.downloader import ensure_model


def test_cache_hit_skips_download(tmp_path):
    cached = tmp_path / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    cached.write_bytes(b"fake-model-data")

    with patch("opencomplai_ai.downloader.get_cache_dir", return_value=tmp_path):
        result = ensure_model("qwen2.5-coder-1.5b")

    assert result == cached


def test_unknown_model_raises():
    with pytest.raises(ValueError, match="Unknown model"):
        ensure_model("totally-fake-model")


def test_saas_model_raises_no_filename():
    with pytest.raises(ValueError, match="no downloadable file"):
        ensure_model("saas")


def test_missing_file_triggers_download(tmp_path):
    mock_hf = MagicMock(
        return_value=str(tmp_path / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")
    )
    (tmp_path / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf").write_bytes(b"downloaded")

    console_mock = MagicMock()
    console_mock.input.return_value = "Y"

    with (
        patch("opencomplai_ai.downloader.get_cache_dir", return_value=tmp_path),
        patch("opencomplai_ai.downloader.Console", return_value=console_mock),
        patch("opencomplai_ai.downloader.Progress") as mock_progress,
        patch("huggingface_hub.hf_hub_download", mock_hf),
    ):
        mock_progress.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_progress.return_value.__exit__ = MagicMock(return_value=False)

        result = ensure_model("qwen2.5-coder-1.5b")

    assert result.name == "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
