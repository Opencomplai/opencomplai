"""SnippetCache resolves locations against an optional root."""

from __future__ import annotations

from opencomplai_core.scanner.snippet_cache import SnippetCache


def _write(root, name="m.py"):
    (root / name).write_text("a\nb\nc\nd\ne\n", encoding="utf-8")


def test_root_resolves_relative_location(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo)
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    cache = SnippetCache(root=repo)
    assert "c" in cache.read_narrow("m.py:3", half_window=0).splitlines()
    assert not cache.unreadable


def test_no_root_keeps_cwd_behaviour(tmp_path, monkeypatch):
    _write(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert SnippetCache().read_narrow("m.py:3", half_window=0) == "c"


def test_absolute_location_with_root(tmp_path):
    _write(tmp_path)
    other = tmp_path / "x"
    other.mkdir()
    cache = SnippetCache(root=other)
    assert cache.read_narrow(f"{tmp_path / 'm.py'}:2", half_window=0) == "b"


def test_unreadable_recorded_only_for_numbered_locations(tmp_path):
    cache = SnippetCache(root=tmp_path)
    assert cache.read("missing.py:3") == ""
    assert cache.read("pkg.json:dep") == ""
    assert cache.unreadable == {"missing.py:3"}
