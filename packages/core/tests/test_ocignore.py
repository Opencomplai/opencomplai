"""`.ocignore` parser, limits, bootstrap, and cache hash."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.scanner.inventory import InventoryLimits
from opencomplai_core.scanner.ocignore import (
    DEFAULT_OCIGNORE_TEMPLATE,
    config_dict_for_hash,
    ensure_ocignore,
    load_ocignore,
    ocignore_content_hash,
    parse_ocignore,
    resolve_ocignore_path,
)


def test_parse_default_template_limits_unlimited():
    cfg = parse_ocignore(DEFAULT_OCIGNORE_TEMPLATE)
    assert cfg.limits.max_files == 0
    assert cfg.limits.max_bytes_per_file == 0
    assert cfg.limits.max_total_bytes == 0
    assert cfg.limits.skip_binary is False
    assert cfg.limits.max_symlink_depth == 5
    assert cfg.limits.max_notebook_cells == 500
    assert ".git/" in cfg.patterns
    assert "node_modules/" in cfg.patterns


def test_parse_limits_section():
    content = """[limits]
max_files = 100
skip_binary = true
max_bytes_per_file = 1024

src/
"""
    cfg = parse_ocignore(content)
    assert cfg.limits.max_files == 100
    assert cfg.limits.skip_binary is True
    assert cfg.limits.max_bytes_per_file == 1024
    assert cfg.patterns == ["src/"]


def test_rejects_negation_and_globstar():
    content = "!secret/\n**/*.log\nok.py\n"
    cfg = parse_ocignore(content)
    assert cfg.patterns == ["ok.py"]
    assert len(cfg.warnings) == 2


def test_rejects_anchored_path():
    content = "/absolute/path\nrelative.py\n"
    cfg = parse_ocignore(content)
    assert cfg.patterns == ["relative.py"]
    assert any("anchored" in w for w in cfg.warnings)


def test_invalid_limit_values_warn_and_default():
    content = """[limits]
max_files = not_a_number
skip_binary = maybe
"""
    cfg = parse_ocignore(content)
    assert cfg.limits.max_files == 0
    assert cfg.limits.skip_binary is False
    assert len(cfg.warnings) >= 2


def test_unknown_limit_key_warns():
    content = "[limits]\nunknown_key = 1\n"
    cfg = parse_ocignore(content)
    assert any("unknown limit" in w for w in cfg.warnings)


def test_bom_and_crlf_tolerant():
    content = "\ufeff[limits]\r\nmax_files = 3\r\n\r\nfoo/\r\n"
    cfg = parse_ocignore(content)
    assert cfg.limits.max_files == 3
    assert "foo/" in cfg.patterns


def test_load_missing_returns_empty_patterns(tmp_path: Path):
    cfg = load_ocignore(tmp_path)
    assert cfg.patterns == []
    assert cfg.limits.max_files == 0


def test_resolve_ocignore_must_be_under_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.ocignore"
    outside.write_text("x/", encoding="utf-8")
    try:
        resolve_ocignore_path(repo, outside)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_ensure_ocignore_creates_file(tmp_path: Path):
    created, path = ensure_ocignore(tmp_path, import_gitignore=False)
    assert created is True
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "[limits]" in text
    assert "node_modules/" in text


def test_ensure_ocignore_imports_gitignore(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("custom_dir/\n# comment\n", encoding="utf-8")
    created, _path = ensure_ocignore(tmp_path, import_gitignore=True)
    assert created is True
    cfg = load_ocignore(tmp_path)
    assert "custom_dir/" in cfg.patterns


def test_ensure_ocignore_idempotent(tmp_path: Path):
    ensure_ocignore(tmp_path, import_gitignore=False)
    created, _ = ensure_ocignore(tmp_path, import_gitignore=False)
    assert created is False


def test_content_hash_stable():
    h1 = ocignore_content_hash("a\nb\n")
    h2 = ocignore_content_hash("a\nb\n")
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_config_dict_for_hash_canonical():
    limits = InventoryLimits(max_files=0, skip_binary=True)
    d1 = config_dict_for_hash(["b/", "a/"], limits, "sha256:abc")
    d2 = config_dict_for_hash(["a/", "b/"], limits, "sha256:abc")
    assert d1["patterns"] == ["a/", "b/"]
    assert d1 == d2
