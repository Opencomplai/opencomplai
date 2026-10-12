"""CL-A1: tree_digest hashes file content under relative paths, nothing else."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.tree_digest import tree_digest


def _file(root: Path, name: str, data: bytes) -> tuple[str, Path]:
    path = root / name
    path.write_bytes(data)
    return name, path


def test_order_independent(tmp_path: Path):
    a = _file(tmp_path, "a.txt", b"one")
    b = _file(tmp_path, "b.txt", b"two")
    assert tree_digest([a, b]) == tree_digest([b, a])
    assert len(tree_digest([a, b])) == 64


def test_content_change_changes_digest(tmp_path: Path):
    before = tree_digest([_file(tmp_path, "a.txt", b"one")])
    after = tree_digest([_file(tmp_path, "a.txt", b"two")])
    assert before != after


def test_crlf_and_lf_hash_the_same(tmp_path: Path):
    lf = tree_digest([_file(tmp_path, "a.txt", b"x\ny\n")])
    crlf = tree_digest([_file(tmp_path, "a.txt", b"x\r\ny\r\n")])
    assert lf == crlf


def test_path_rename_changes_digest(tmp_path: Path):
    _, path = _file(tmp_path, "a.txt", b"one")
    assert tree_digest([("a.txt", path)]) != tree_digest([("b.txt", path)])


def test_missing_file_is_stable_marker(tmp_path: Path):
    gone = ("gone.txt", tmp_path / "gone.txt")
    folder = tmp_path / "dir"
    folder.mkdir()
    assert tree_digest([gone]) == tree_digest([gone])
    # A directory and a missing path both hash the unreadable marker.
    assert tree_digest([gone]) == tree_digest([("gone.txt", folder)])
    # The marker is not the hash of empty content.
    (tmp_path / "empty.txt").write_bytes(b"")
    assert tree_digest([gone]) != tree_digest([("gone.txt", tmp_path / "empty.txt")])
