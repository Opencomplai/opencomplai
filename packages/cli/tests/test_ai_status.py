"""`opencomplai ai status` must describe backends that need no download truthfully.

codebert-onnx is a deterministic code-signal matcher and saas is a cloud
client: neither has a local artifact, so status must not print the
"model not yet downloaded" line (it implied a download was missing) and must
not label the matcher as an ONNX Runtime backend. The cache section itself
stays: GGUF models downloaded earlier still occupy the cache directory.
"""

from __future__ import annotations

import pytest

pytest.importorskip("opencomplai_ai")

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _status(monkeypatch, tmp_path, model_id: str) -> str:
    monkeypatch.setattr("opencomplai_ai.config.get_active_model", lambda: model_id)
    # A cache dir that does not exist: the case that used to print
    # "(empty — model not yet downloaded)".
    monkeypatch.setattr(
        "opencomplai_ai.config.get_cache_dir", lambda: tmp_path / "no-cache"
    )
    result = runner.invoke(app, ["ai", "status"])
    assert result.exit_code == 0, result.output
    return result.output


@pytest.mark.parametrize("model_id", ["codebert-onnx", "saas"])
def test_status_for_no_download_backend_has_no_not_yet_downloaded_line(
    monkeypatch, tmp_path, model_id
):
    out = _status(monkeypatch, tmp_path, model_id)

    assert "not yet downloaded" not in out


@pytest.mark.parametrize("model_id", ["codebert-onnx", "saas"])
def test_status_for_no_download_backend_still_lists_an_existing_cache(
    monkeypatch, tmp_path, model_id
):
    # A GGUF model downloaded before switching backend still uses disk space;
    # status must keep showing it.
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "earlier-model.gguf").write_bytes(b"x" * 16)
    monkeypatch.setattr("opencomplai_ai.config.get_active_model", lambda: model_id)
    monkeypatch.setattr("opencomplai_ai.config.get_cache_dir", lambda: cache)

    result = runner.invoke(app, ["ai", "status"])

    assert result.exit_code == 0, result.output
    assert "cache dir" in result.output
    assert "cache size" in result.output
    assert "earlier-model.gguf" in result.output
    assert "not yet downloaded" not in result.output


def test_status_for_codebert_onnx_reports_deterministic_runtime(monkeypatch, tmp_path):
    out = _status(monkeypatch, tmp_path, "codebert-onnx")

    assert "deterministic" in out
    assert "onnxruntime" not in out
    assert "CodeBERT" not in out


def test_status_for_gguf_model_still_reports_missing_download(monkeypatch, tmp_path):
    out = _status(monkeypatch, tmp_path, "qwen2.5-coder-1.5b")

    assert "llama-cpp" in out
    assert "not yet downloaded" in out


def _status_with_cache(monkeypatch, cache, model_id: str) -> str:
    monkeypatch.setattr("opencomplai_ai.config.get_active_model", lambda: model_id)
    monkeypatch.setattr("opencomplai_ai.config.get_cache_dir", lambda: cache)
    result = runner.invoke(app, ["ai", "status"])
    assert result.exit_code == 0, result.output
    return result.output


def test_status_counts_nested_cache_file(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    (cache / "codebert-base").mkdir(parents=True)
    (cache / "codebert-base" / "model.onnx").write_bytes(b"x" * (3 * 1024 * 1024))

    out = _status_with_cache(monkeypatch, cache, "codebert-onnx")

    assert "cache size    : 3 MB" in out
    assert "codebert-base/model.onnx" in out
    assert "not yet downloaded" not in out


def test_status_small_nested_cache_file_reports_less_than_one_mb(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    (cache / "sub").mkdir(parents=True)
    (cache / "sub" / "f.bin").write_bytes(b"x" * 10)

    out = _status_with_cache(monkeypatch, cache, "codebert-onnx")

    assert "<1 MB" in out


@pytest.mark.parametrize("sub", [False, True])
def test_status_empty_cache_dir_prints_not_yet_downloaded(monkeypatch, tmp_path, sub):
    cache = tmp_path / "cache"
    cache.mkdir()
    if sub:
        (cache / "empty-sub").mkdir()

    out = _status_with_cache(monkeypatch, cache, "qwen2.5-coder-1.5b")

    assert "not yet downloaded" in out
    assert "cache size" not in out


@pytest.mark.parametrize("model_id", ["codebert-onnx", "saas"])
def test_status_empty_cache_dir_for_no_download_backend_has_no_not_yet_downloaded_line(
    monkeypatch, tmp_path, model_id
):
    cache = tmp_path / "cache"
    cache.mkdir()

    out = _status_with_cache(monkeypatch, cache, model_id)

    assert "not yet downloaded" not in out


@pytest.mark.parametrize("model_id", ["codebert-onnx", "saas"])
def test_status_size_mb_zero_prints_unknown(monkeypatch, tmp_path, model_id):
    out = _status(monkeypatch, tmp_path, model_id)

    assert "size          : unknown" in out
    assert "~0 MB" not in out


def test_status_known_size_still_prints_approximate_mb(monkeypatch, tmp_path):
    out = _status(monkeypatch, tmp_path, "qwen2.5-coder-1.5b")

    assert "~1000 MB" in out
