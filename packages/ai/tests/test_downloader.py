"""Tests for opencomplai_ai.downloader."""

from unittest.mock import MagicMock, patch

import pytest
from opencomplai_ai.downloader import ensure_model
from opencomplai_ai.models import ModelNotInstalledError


def test_cache_hit_skips_download(tmp_path):
    cached = tmp_path / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    cached.write_bytes(b"fake-model-data")

    with (
        patch("opencomplai_ai.downloader.get_cache_dir", return_value=tmp_path),
        patch("opencomplai_ai.downloader.verify_artifact"),
    ):
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
        patch("opencomplai_ai.downloader.verify_artifact"),
        # requires_deep=True for this model; the base install in this test
        # suite has no llama-cpp-python, so without this the new
        # finding-48.10 gate below would (correctly) refuse before download.
        patch.dict("sys.modules", {"llama_cpp": MagicMock()}),
    ):
        mock_progress.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_progress.return_value.__exit__ = MagicMock(return_value=False)

        result = ensure_model("qwen2.5-coder-1.5b")

    assert result.name == "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"


def test_missing_deep_dependency_refuses_before_download(tmp_path):
    """Finding 48.10: a requires_deep model with no cached file and no
    llama-cpp-python installed must fail fast with an actionable message,
    never reach hf_hub_download, and never prompt for confirmation."""
    mock_hf = MagicMock()
    console_mock = MagicMock()

    with (
        patch("opencomplai_ai.downloader.get_cache_dir", return_value=tmp_path),
        patch("opencomplai_ai.downloader.Console", return_value=console_mock),
        patch("huggingface_hub.hf_hub_download", mock_hf),
        patch.dict("sys.modules", {"llama_cpp": None}),
    ):
        with pytest.raises(ModelNotInstalledError, match="llama-cpp-python"):
            ensure_model("qwen2.5-coder-1.5b")

    mock_hf.assert_not_called()
    console_mock.input.assert_not_called()
