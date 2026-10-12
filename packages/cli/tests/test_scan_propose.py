"""`scan --propose`: a classification suggested from code, written as a file."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from opencomplai_core.classification_proposal import (
    PROPOSAL_FILENAME,
    load_proposal,
    proposal_digest,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.models import SystemManifest
from typer.testing import CliRunner

runner = CliRunner()

_SCREEN = (
    "from sklearn.ensemble import RandomForestClassifier\n\n\n"
    "def screen(applicants):\n"
    "    ranked = rank_candidates(applicants)\n"
    "    return ranked\n"
)
_COMMON = (
    "--ai-model",
    "codebert-onnx",
    "--no-emit-evidence",
    "--no-ocignore-bootstrap",
)


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "system-manifest.json"
    path.write_text(
        SystemManifest(
            system_id="prop-sys", intended_purpose="customer support chatbot"
        ).model_dump_json(),
        encoding="utf-8",
    )
    return path


def _employment_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    for name in ("a", "b", "c"):
        (repo / "src" / f"{name}.py").write_text(_SCREEN, encoding="utf-8")
    return repo


def _scan(tmp_path: Path, repo: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(_manifest(tmp_path)),
            "--repo-root",
            str(repo),
            *_COMMON,
            *extra,
        ],
    )


def test_scan_propose_writes_file(tmp_path: Path) -> None:
    repo = _employment_repo(tmp_path)
    plain = _scan(tmp_path, repo, "-o", "json")
    assert plain.exit_code == 0, plain.output
    payload = json.loads(plain.stdout)["payload"]
    assert not (repo / PROPOSAL_FILENAME).exists()

    result = _scan(tmp_path, repo, "--propose", "-o", "json")
    assert result.exit_code == 0, result.output
    assert "Proposal written" in result.stderr
    json.loads(result.stdout)  # the JSON envelope on stdout stays clean

    doc = load_proposal(repo / PROPOSAL_FILENAME)
    manifest = SystemManifest.model_validate_json(
        (tmp_path / "system-manifest.json").read_text(encoding="utf-8")
    )
    assert doc["status"] == "unconfirmed"
    assert doc["scan_input_digest"] == payload["input_digest"]
    assert doc["proposal_sha256"] == proposal_digest(doc)
    assert doc["system_id"] == "prop-sys"
    assert doc["manifest_fingerprint"] == fingerprint_manifest(manifest)
    assert doc["area"] == "employment"
    assert doc["proposal"]["proposed_annex_iii_area"] == 4
    assert doc["confidence"] == "medium"
    assert sorted(ln["location"] for ln in doc["evidence"]) == [
        "src/a.py:5",
        "src/b.py:5",
        "src/c.py:5",
    ]


def test_scan_without_propose_writes_nothing(tmp_path: Path) -> None:
    repo = _employment_repo(tmp_path)
    result = _scan(tmp_path, repo, "--ai-intent")
    assert result.exit_code == 0, result.output
    assert not (repo / PROPOSAL_FILENAME).exists()


def test_propose_rejected_with_quick(tmp_path: Path) -> None:
    repo = _employment_repo(tmp_path)
    result = _scan(tmp_path, repo, "--quick", "--propose")
    assert result.exit_code == 2, result.output
    assert not (repo / PROPOSAL_FILENAME).exists()


def test_propose_on_empty_repo_proposes_none(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# nothing here\n", encoding="utf-8")
    result = _scan(tmp_path, repo, "--propose")
    assert result.exit_code == 0, result.output
    doc = load_proposal(repo / PROPOSAL_FILENAME)
    assert doc["area"] == "none"
    assert doc["confidence"] == "none"
    assert doc["proposal"]["proposed_annex_iii_area"] is None
    assert doc["evidence"] == []


def test_scan_ignores_existing_proposal_file(tmp_path: Path) -> None:
    repo = _employment_repo(tmp_path)
    args = ("--ai-intent", "-o", "json")
    before = json.loads(_scan(tmp_path, repo, *args).stdout)["payload"]
    assert before["eu_ai_scan"]["high_risk"], "fixture must produce findings"
    assert _scan(tmp_path, repo, "--propose").exit_code == 0
    assert (repo / PROPOSAL_FILENAME).is_file()
    after = json.loads(_scan(tmp_path, repo, *args).stdout)["payload"]
    assert after["detected_categories"] == before["detected_categories"]
    # The input digest is content-based, so the extra file moves it (and the
    # report hash that covers it); nothing the detectors produced may move.
    assert after["input_digest"] != before["input_digest"]
    run_specific = {"scan_id", "generated_at", "input_digest", "report_hash"}
    assert {k: v for k, v in after.items() if k not in run_specific} == {
        k: v for k, v in before.items() if k not in run_specific
    }


def test_propose_with_legacy_exits_2_writes_nothing(tmp_path: Path) -> None:
    repo = _employment_repo(tmp_path)
    result = _scan(tmp_path, repo, "--propose", "--ai-legacy")
    assert result.exit_code == 2, result.output
    assert not (repo / PROPOSAL_FILENAME).exists()
