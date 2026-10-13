"""The written-files manifest keeps tool-written report files out of the tree digest.

A report file the tool wrote (junit, sarif, a summary) is listed with its content
hash in ``.opencomplai/written-files.json``. The digest drops a listed file only
while its content still equals the recorded hash. A missing or corrupt manifest
reads as empty, which is the 0.12.0 behaviour. Real ``run_scan`` over ``tmp_path``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from opencomplai_core.classification_proposal import (
    TOOL_WRITTEN_NAMES,
    WRITTEN_FILES_MANIFEST,
)
from opencomplai_core.models import CorroborationReport
from opencomplai_core.scan_engine import _digest, input_digest, run_scan
from opencomplai_core.scanner.inventory import build_repo_inventory
from opencomplai_core.tree_digest import _content_hash
from opencomplai_core.written_files import (
    load_written_files,
    record_written_file,
    unchanged_written_paths,
)

PURPOSE = "customer support chatbot"
SOURCE = "def answer(q):\n    return 'ok'\n"


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text(SOURCE, encoding="utf-8")
    return repo


def _scan(repo: Path) -> CorroborationReport:
    return run_scan("written-sys", "HEAD", repo, PURPOSE)


def _report(repo: Path, text: str = "<testsuite/>\n") -> Path:
    path = repo / "reports" / "junit.xml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_listed_file_with_matching_hash_is_excluded(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    baseline = _scan(repo)
    junit = _report(repo)
    record_written_file(repo, junit)
    after = _scan(repo)
    assert after.source_tree_sha256 == baseline.source_tree_sha256
    assert after.source_tree_sha256_legacy != baseline.source_tree_sha256
    assert unchanged_written_paths(repo) == {"reports/junit.xml"}


def test_unlisted_report_file_still_moves_digest(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    baseline = _scan(repo)
    _report(repo)
    after = _scan(repo)
    assert after.source_tree_sha256 != baseline.source_tree_sha256


def test_listed_file_edited_after_recording_is_included(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    baseline = _scan(repo)
    junit = _report(repo)
    record_written_file(repo, junit)
    junit.write_text("<testsuite failures='1'/>\n", encoding="utf-8")
    after = _scan(repo)
    assert after.source_tree_sha256 != baseline.source_tree_sha256
    assert unchanged_written_paths(repo) == frozenset()


@pytest.mark.parametrize(
    "content",
    [
        None,
        "",
        "not json",
        "[]",
        json.dumps({"schema_version": 2, "files": {"reports/junit.xml": "0" * 64}}),
        json.dumps({"schema_version": 1, "files": {"reports/junit.xml": 7}}),
        json.dumps({"schema_version": 1, "files": ["reports/junit.xml"]}),
    ],
    ids=[
        "missing",
        "empty",
        "not-json",
        "array",
        "wrong-schema",
        "non-string-hash",
        "files-not-object",
    ],
)
def test_corrupt_or_missing_manifest_falls_back_to_legacy(
    tmp_path: Path, content: str | None
) -> None:
    repo = _repo(tmp_path)
    _report(repo)
    if content is not None:
        manifest = repo / WRITTEN_FILES_MANIFEST
        manifest.parent.mkdir()
        manifest.write_text(content, encoding="utf-8")
    assert load_written_files(repo) == {}
    report = _scan(repo)
    assert report.source_tree_sha256 == report.source_tree_sha256_legacy


def test_manifest_file_itself_does_not_move_digest(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    baseline = _scan(repo)
    sidecar = repo / TOOL_WRITTEN_NAMES[0]
    sidecar.write_text("{}\n", encoding="utf-8")
    with_sidecar = _scan(repo)
    record_written_file(repo, _report(repo))  # a non-sidecar name creates the manifest
    inventory = build_repo_inventory(repo)
    assert WRITTEN_FILES_MANIFEST in {e.rel_path for e in inventory.entries}
    after = _scan(repo)
    for report in (with_sidecar, after):
        assert report.source_tree_sha256 == baseline.source_tree_sha256
    assert with_sidecar.source_tree_sha256_legacy == baseline.source_tree_sha256


def test_record_is_atomic_best_effort_and_inside_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path / "elsewhere.xml"
    outside.write_text("x\n", encoding="utf-8")
    record_written_file(repo, outside)
    record_written_file(repo, repo / "missing.xml")
    assert not (repo / WRITTEN_FILES_MANIFEST).exists()

    first = _report(repo)
    second = repo / "summary.md"
    second.write_text("# summary\n", encoding="utf-8")
    record_written_file(repo, first)
    record_written_file(repo, second)
    assert set(load_written_files(repo)) == {"reports/junit.xml", "summary.md"}
    doc = (repo / WRITTEN_FILES_MANIFEST).read_text(encoding="utf-8")
    assert doc.endswith("\n")
    assert list(json.loads(doc)["files"]) == sorted(json.loads(doc)["files"])
    assert not list((repo / ".opencomplai").glob("*.tmp"))

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("read-only")

    monkeypatch.setattr(os, "replace", boom)
    third = repo / "third.sarif"
    third.write_text("{}\n", encoding="utf-8")
    record_written_file(repo, third)  # must not raise
    assert set(load_written_files(repo)) == {"reports/junit.xml", "summary.md"}
    assert not list((repo / ".opencomplai").glob("*.tmp"))


def test_no_manifest_means_aware_equals_legacy_and_digest_unchanged(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    report = _scan(repo)
    assert not (repo / WRITTEN_FILES_MANIFEST).exists()
    assert report.source_tree_sha256 == report.source_tree_sha256_legacy
    inventory = build_repo_inventory(repo)
    # The input digest is built from the legacy value, so nothing for a tree
    # without a manifest moves and no SCANNER_VERSION bump is needed.
    assert input_digest(inventory, "HEAD", "cfg") == _digest(
        report.source_tree_sha256_legacy, "HEAD", "cfg"
    )


def test_new_fields_are_never_serialised(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report = _scan(repo)
    assert report.source_tree_sha256
    dumped = report.model_dump_json()
    assert "source_tree_sha256" not in dumped
    assert report.source_tree_sha256_legacy not in dumped
    before = report.report_hash
    other = report.model_copy(update={"source_tree_sha256_legacy": "x" * 64})
    assert other.model_dump_json() == dumped
    assert other.report_hash == before


def test_tool_named_file_is_not_recorded(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    sidecar = repo / "scan-report.json"
    sidecar.write_text("{}\n", encoding="utf-8")
    record_written_file(repo, sidecar)
    assert not (repo / ".opencomplai").exists()


def test_tampered_manifest_keys_outside_root_are_ignored(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    inside = _report(repo)
    record_written_file(repo, inside)
    manifest = repo / WRITTEN_FILES_MANIFEST
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["files"][str(outside)] = _content_hash(outside)
    doc["files"]["../outside.txt"] = _content_hash(outside)
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    assert unchanged_written_paths(repo) == {"reports/junit.xml"}
