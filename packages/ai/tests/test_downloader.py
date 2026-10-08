"""Tests for opencomplai_ai.downloader."""

from unittest.mock import MagicMock, patch

import pytest
from opencomplai_ai.downloader import _ensure_onnx_export, ensure_model
from opencomplai_ai.egress import OfflineModeError
from opencomplai_ai.models import MODEL_CATALOG, ModelNotInstalledError


def test_cache_hit_skips_download(tmp_path):
    cached = tmp_path / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    cached.write_bytes(b"fake-model-data")

    # The catalogue now pins a real sha256; these fake bytes are not that file.
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
        patch("opencomplai_ai.downloader.verify_artifact"),
        patch("huggingface_hub.hf_hub_download", mock_hf),
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


def test_codebert_onnx_still_routes_to_the_export_path(tmp_path):
    # ensure_model used to dispatch on runtime == "onnxruntime"; relabelling
    # the runtime must not turn the Python-API export into a plain-file
    # download of a tarball that does not exist on the Hub.
    exported = tmp_path / "model.onnx"
    with (
        patch(
            "opencomplai_ai.downloader._ensure_onnx_export", return_value=exported
        ) as export,
        patch("huggingface_hub.hf_hub_download") as hf,
    ):
        assert ensure_model("codebert-onnx") == exported

    export.assert_called_once()
    hf.assert_not_called()


def _printed(console_mock) -> str:
    return "\n".join(
        str(c.args[0]) for c in console_mock.print.call_args_list if c.args
    )


def test_onnx_export_prompt_names_the_export_not_the_matcher(tmp_path):
    # The catalog display_name describes the deterministic classifier. The
    # export prompt must name the export itself, and say that scans do not use
    # its output.
    console_mock = MagicMock()

    with (
        patch("opencomplai_ai.downloader.get_cache_dir", return_value=tmp_path),
        patch("opencomplai_ai.downloader.require_online"),
        patch("opencomplai_ai.downloader.Console", return_value=console_mock),
        patch("opencomplai_ai.downloader.stdin_is_interactive", return_value=False),
        # Nothing may reach the Hub or optimum from this test.
        patch.dict("sys.modules", {"optimum": None, "optimum.onnxruntime": None}),
    ):
        with pytest.raises(RuntimeError) as excinfo:
            _ensure_onnx_export(MODEL_CATALOG["codebert-onnx"])

    prompt = _printed(console_mock)
    assert "CodeBERT ONNX export" in prompt
    assert "Deterministic code-signal matcher" not in prompt
    assert "future scans" not in prompt
    assert "Scans do not use it" in prompt
    assert "Deterministic code-signal matcher" not in str(excinfo.value)


def test_onnx_export_offline_error_names_the_export_not_the_matcher(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENCOMPLAI_OFFLINE", "1")

    with patch("opencomplai_ai.downloader.get_cache_dir", return_value=tmp_path):
        with pytest.raises(OfflineModeError) as excinfo:
            _ensure_onnx_export(MODEL_CATALOG["codebert-onnx"])

    assert "CodeBERT ONNX export" in str(excinfo.value)
    assert "Deterministic code-signal matcher" not in str(excinfo.value)
