"""_preload_ai_model must not call ensure_model for backends that need no
local setup.

codebert-onnx is a deterministic code-signal matcher (no artifact, nothing
downloaded on the classification path) and saas is a cloud API client, yet
the pre-scan preload routed both through ensure_model — for codebert-onnx
that meant the separate, optional ONNX-export path: an interactive ~440 MB
download prompt, or in non-interactive runs a RuntimeError that silently
disabled --ai-intent for a backend that needs zero setup.
"""

from __future__ import annotations

import sys

import pytest

pytest.importorskip("opencomplai_ai")

from opencomplai_cli.main import _preload_ai_model, _require_ai_plugin


def _forbid_ensure_model(monkeypatch):
    def _boom(model_id):
        raise AssertionError(f"ensure_model must not be called for {model_id!r}")

    monkeypatch.setattr("opencomplai_ai.downloader.ensure_model", _boom)


def test_preload_skips_ensure_model_for_codebert_onnx(monkeypatch):
    _forbid_ensure_model(monkeypatch)

    assert _preload_ai_model("codebert-onnx") is True


def test_preload_skips_ensure_model_for_saas(monkeypatch):
    _forbid_ensure_model(monkeypatch)

    assert _preload_ai_model("saas") is True


def test_preload_still_calls_ensure_model_for_gguf_models(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "opencomplai_ai.downloader.ensure_model",
        lambda model_id: calls.append(model_id),
    )

    assert _preload_ai_model("qwen2.5-coder-1.5b") is True
    assert calls == ["qwen2.5-coder-1.5b"]


def test_preload_skip_message_keeps_the_deep_extra_in_the_install_command(
    monkeypatch, tmp_path, capsys
):
    # Rich reads "[deep]" as a style tag and drops it unless the message is
    # escaped, which turned the remediation into "pip install 'opencomplai-ai'".
    # No cached file and no llama-cpp-python: the real ensure_model refuses
    # with the real install hint.
    monkeypatch.setattr("opencomplai_ai.downloader.get_cache_dir", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "llama_cpp", None)

    assert _preload_ai_model("qwen2.5-coder-1.5b") is False

    err = capsys.readouterr().err
    assert "AI intent skipped" in err
    assert "pip install 'opencomplai-ai[deep]'" in err


def test_missing_plugin_message_keeps_the_deep_extra_in_the_install_command(
    monkeypatch, capsys
):
    monkeypatch.setitem(sys.modules, "opencomplai_ai", None)

    with pytest.raises(SystemExit):
        _require_ai_plugin()

    assert "pip install 'opencomplai-ai[deep]'" in capsys.readouterr().err
