"""Repo inventory — ocignore patterns, limits, skip reasons."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.models import EvidenceScope
from opencomplai_core.scanner.inventory import InventoryLimits, build_repo_inventory

DEFAULT_IGNORE = [
    "node_modules/",
    "vendor/",
    ".git/",
]


def _write(tmp_path: Path, rel: str, content: str = "x") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_honors_ignore_patterns(tmp_path: Path):
    _write(tmp_path, "ignored/secret.py", "openai")
    _write(tmp_path, "src/app.py", "import openai")
    inv = build_repo_inventory(tmp_path, ignore_patterns=["ignored/*.py"])
    rels = {e.rel_path for e in inv.entries}
    assert "src/app.py" in rels
    assert "ignored/secret.py" not in rels
    assert inv.skip_reasons.get("ignored", 0) >= 1


def test_skips_node_modules_and_vendor(tmp_path: Path):
    _write(tmp_path, "node_modules/pkg/index.js", "openai")
    _write(tmp_path, "vendor/lib.py", "torch")
    _write(tmp_path, "src/main.py", "ok")
    inv = build_repo_inventory(tmp_path, ignore_patterns=DEFAULT_IGNORE)
    rels = {e.rel_path for e in inv.entries}
    assert "src/main.py" in rels
    assert not any("node_modules" in r for r in rels)


def test_classifies_test_scope(tmp_path: Path):
    _write(tmp_path, "tests/test_app.py", "def test_x(): pass")
    _write(tmp_path, "src/app.py", "def main(): pass")
    inv = build_repo_inventory(tmp_path)
    scopes = {e.rel_path: e.scope for e in inv.entries}
    assert scopes["tests/test_app.py"] == EvidenceScope.TEST
    assert scopes["src/app.py"] == EvidenceScope.PROD


def test_rejects_path_outside_repo(tmp_path: Path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    inv = build_repo_inventory(tmp_path)
    rels = {e.rel_path for e in inv.entries}
    assert "outside.txt" not in rels


def test_huge_file_skipped(tmp_path: Path):
    _write(tmp_path, "small.py", "x")
    big = tmp_path / "huge.py"
    big.write_bytes(b"x" * 3_000_000)
    limits = InventoryLimits(max_bytes_per_file=1000)
    inv = build_repo_inventory(tmp_path, limits=limits)
    rels = {e.rel_path for e in inv.entries}
    assert "small.py" in rels
    assert "huge.py" not in rels
    assert inv.skip_reasons.get("oversized", 0) == 1
    assert any("max_bytes_per_file" in x for x in inv.limits_hit)


def test_skip_binary_when_enabled(tmp_path: Path):
    binary = tmp_path / "data.bin"
    binary.write_bytes(b"\x00\x01\x02")
    _write(tmp_path, "src/app.py", "ok")
    limits = InventoryLimits(skip_binary=True)
    inv = build_repo_inventory(tmp_path, limits=limits)
    rels = {e.rel_path for e in inv.entries}
    assert "src/app.py" in rels
    assert "data.bin" not in rels
    assert inv.skip_reasons.get("binary", 0) == 1


def test_unlimited_limits_by_default(tmp_path: Path):
    big = tmp_path / "large.py"
    big.write_bytes(b"x" * 5_000_000)
    inv = build_repo_inventory(tmp_path, limits=InventoryLimits())
    rels = {e.rel_path for e in inv.entries}
    assert "large.py" in rels
