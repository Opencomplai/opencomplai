"""Tests for the --check mode of scripts/generate_principle_docs.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_principle_docs.py"

_spec = importlib.util.spec_from_file_location("generate_principle_docs", SCRIPT_PATH)
generate_principle_docs = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(generate_principle_docs)


def _output(tmp_path: Path) -> Path:
    return tmp_path / "eu-ai-act-principles.md"


def test_check_exits_zero_when_up_to_date(tmp_path, monkeypatch) -> None:
    output = _output(tmp_path)
    output.write_text(generate_principle_docs.render(), encoding="utf-8")
    monkeypatch.setattr(generate_principle_docs, "OUTPUT_PATH", output)

    assert generate_principle_docs.main(["--check"]) == 0


def test_check_exits_one_when_stale(tmp_path, monkeypatch) -> None:
    output = _output(tmp_path)
    output.write_text("# stale\n", encoding="utf-8")
    monkeypatch.setattr(generate_principle_docs, "OUTPUT_PATH", output)

    assert generate_principle_docs.main(["--check"]) == 1


def test_check_does_not_write(tmp_path, monkeypatch) -> None:
    output = _output(tmp_path)
    stale = "# stale\n"
    output.write_text(stale, encoding="utf-8")
    monkeypatch.setattr(generate_principle_docs, "OUTPUT_PATH", output)

    generate_principle_docs.main(["--check"])

    assert output.read_text(encoding="utf-8") == stale
