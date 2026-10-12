from __future__ import annotations

import os

import pytest
from opencomplai_cli.ai_status import cache_files, format_cache_size, spec_size_label


def test_cache_files_counts_nested_files_sorted(tmp_path):
    (tmp_path / "b.gguf").write_bytes(b"x" * 5)
    (tmp_path / "codebert-base").mkdir()
    (tmp_path / "codebert-base" / "model.onnx").write_bytes(b"y" * 7)
    assert cache_files(tmp_path) == [("b.gguf", 5), ("codebert-base/model.onnx", 7)]


def test_cache_files_ignores_missing_dir_and_empty_subdirs(tmp_path):
    assert cache_files(tmp_path / "nope") == []
    (tmp_path / "a" / "b").mkdir(parents=True)
    assert cache_files(tmp_path) == []


def test_cache_files_skips_symlinks(tmp_path):
    target = tmp_path / "real.bin"
    target.write_bytes(b"z")
    cache = tmp_path / "cache"
    cache.mkdir()
    try:
        os.symlink(target, cache / "link.bin")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    assert cache_files(cache) == []


def test_format_cache_size_boundaries():
    assert format_cache_size(0) == "0 MB"
    assert format_cache_size(1) == "<1 MB"
    assert format_cache_size(1048575) == "<1 MB"
    assert format_cache_size(1048576) == "1 MB"
    assert format_cache_size(3 * 1048576 + 5) == "3 MB"


def test_spec_size_label():
    assert spec_size_label(0) == "unknown"
    assert spec_size_label(-1) == "unknown"
    assert spec_size_label(1000) == "~1000 MB"
