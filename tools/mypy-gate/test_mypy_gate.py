"""Tests for mypy_gate.py. ``run`` is monkeypatched; mypy is never invoked."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add the tool directory to sys.path so we can import it directly
sys.path.insert(0, str(Path(__file__).parent))

import mypy_gate
import pytest


def _gate(monkeypatch, tmp_path, baseline: dict, counts: dict) -> None:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(mypy_gate, "BASELINE", path)
    monkeypatch.setattr(mypy_gate, "run", lambda pkg_dir: counts[pkg_dir.name])


_BASE = {"core": 5, "sdk-python": 2, "mypy_version": "1.0.0"}


def test_parse_error_count_success():
    assert (
        mypy_gate.parse_error_count("Success: no issues found in 2 source files\n") == 0
    )


def test_parse_error_count_found_errors():
    out = "a.py:1: error: x  [misc]\nFound 112 errors in 19 files (checked 131 source files)\n"
    assert mypy_gate.parse_error_count(out) == 112
    assert (
        mypy_gate.parse_error_count("Found 1 error in 1 file (checked 1 source file)")
        == 1
    )


def test_parse_error_count_rejects_garbage():
    with pytest.raises(ValueError, match="no mypy summary"):
        mypy_gate.parse_error_count("Traceback (most recent call last):\nboom")


def test_gate_passes_at_baseline(monkeypatch, tmp_path, capsys):
    _gate(monkeypatch, tmp_path, _BASE, {"core": 5, "sdk-python": 2})
    assert mypy_gate.main(["--check"]) == 0
    assert "below baseline" not in capsys.readouterr().out


def test_gate_below_baseline_passes_with_notice(monkeypatch, tmp_path, capsys):
    _gate(monkeypatch, tmp_path, _BASE, {"core": 4, "sdk-python": 2})
    assert mypy_gate.main([]) == 0
    assert "below baseline" in capsys.readouterr().out


def test_gate_fails_when_errors_exceed_baseline(monkeypatch, tmp_path, capsys):
    _gate(monkeypatch, tmp_path, _BASE, {"core": 5, "sdk-python": 3})
    assert mypy_gate.main(["--check"]) == 1
    assert "sdk-python: 3 mypy errors (baseline 2, delta +1)" in capsys.readouterr().out


def test_baseline_json_shape():
    data = json.loads(mypy_gate.BASELINE.read_text(encoding="utf-8"))
    assert set(data) == {"core", "sdk-python", "mypy_version"}
    for name in mypy_gate.PACKAGES:
        assert isinstance(data[name], int)
        assert data[name] >= 0
    assert isinstance(data["mypy_version"], str)
    assert data["mypy_version"].count(".") >= 1
