"""The code digest `scan --propose` stores and `check` compares.

``source_tree_sha256`` is commit-independent and leaves out the files the tool
writes itself (the proposal file, its confirmation record and ``.ocignore``), so
writing them never makes a confirmed proposal look stale.
"""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_core.classification_proposal import (
    PROPOSAL_FILENAME,
    TOOL_WRITTEN_NAMES,
)
from opencomplai_core.models import CorroborationReport
from opencomplai_core.scan_engine import run_scan

PURPOSE = "customer support chatbot"
SOURCE = (
    "import face_recognition\n"
    "def identify(img):\n"
    "    return face_recognition.face_locations(img)\n"
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "face.py").write_text(SOURCE, encoding="utf-8")
    (repo / "requirements.txt").write_text("face_recognition\n", encoding="utf-8")
    return repo


def _scan(repo: Path, commit_ref: str = "HEAD"):
    return run_scan("tree-sys", commit_ref, repo, PURPOSE)


def test_proposal_file_and_record_do_not_move_digest(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = _scan(repo)
    assert before.source_tree_sha256
    (repo / PROPOSAL_FILENAME).write_text('{"status": "unconfirmed"}\n', "utf-8")
    records = repo / ".opencomplai" / "acceptances"
    records.mkdir(parents=True)
    (records / "tree-sys.classification_proposal_confirmation.json").write_text(
        '{"record_type": "classification_proposal_confirmation"}\n', "utf-8"
    )
    after = _scan(repo)
    assert after.input_digest == before.input_digest
    assert after.source_tree_sha256 == before.source_tree_sha256
    assert after.detected_categories == before.detected_categories


def test_source_edit_moves_tree_digest(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = _scan(repo)
    (repo / "src" / "face.py").write_text(SOURCE + "# edited\n", encoding="utf-8")
    after = _scan(repo)
    assert after.source_tree_sha256 != before.source_tree_sha256
    assert after.input_digest != before.input_digest


def test_ocignore_file_does_not_move_tree_digest(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = _scan(repo)
    (repo / ".ocignore").write_text("# a comment only\n", encoding="utf-8")
    after = _scan(repo)
    assert after.source_tree_sha256 == before.source_tree_sha256


def test_nested_file_with_a_tool_name_still_moves_digest(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = _scan(repo)
    (repo / "src" / PROPOSAL_FILENAME).write_text("{}\n", encoding="utf-8")
    assert _scan(repo).source_tree_sha256 != before.source_tree_sha256


def test_check_sidecars_do_not_change_the_code_digest(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "out").mkdir()
    base = _scan(repo).source_tree_sha256
    literal = ("scan-report.json", "eval-report.json", "compliance-artifact.json")
    assert set(literal) <= set(TOOL_WRITTEN_NAMES)
    for name in literal:
        for path in (repo / name, repo / "out" / name):
            path.write_text("{}\n", encoding="utf-8")
            assert _scan(repo).source_tree_sha256 == base
            path.write_text('{"edited": true}\n', encoding="utf-8")
            assert _scan(repo).source_tree_sha256 == base
            path.unlink()
            assert _scan(repo).source_tree_sha256 == base
    (repo / "src" / "face.py").write_text(SOURCE + "# edited\n", encoding="utf-8")
    assert _scan(repo).source_tree_sha256 != base


def test_tree_digest_independent_of_commit_ref(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    head = _scan(repo, "HEAD")
    pinned = _scan(repo, "c" * 40)
    assert head.source_tree_sha256 == pinned.source_tree_sha256
    assert head.input_digest != pinned.input_digest


def test_proposal_status_is_omitted_when_none_and_serialised_when_set(
    tmp_path: Path,
) -> None:
    report = _scan(_repo(tmp_path))
    assert report.proposal_status is None
    plain = json.loads(report.model_dump_json())
    assert "proposal_status" not in plain
    assert "source_tree_sha256" not in plain  # in-process only

    report.proposal_status = "stale"
    dumped = json.loads(report.model_dump_json(indent=2))
    assert dumped["proposal_status"] == "stale"
    assert "source_tree_sha256" not in dumped
    # The sidecar text round-trips into the model.
    again = CorroborationReport.model_validate_json(report.model_dump_json())
    assert again.proposal_status == "stale"
