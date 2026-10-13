"""`scan --propose`: a classification suggested from code, written as a file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from opencomplai_cli.main import app
from opencomplai_core.classification_proposal import (
    PROPOSAL_FILENAME,
    load_proposal,
    proposal_digest,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.models import SystemManifest
from opencomplai_core.scan_engine import run_scan
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
    # The proposal file is written by the tool, so the input digest leaves it
    # out: writing it must not make a proposal look stale.
    assert after["input_digest"] == before["input_digest"]
    run_specific = {"scan_id", "generated_at", "input_digest", "report_hash"}
    assert {k: v for k, v in after.items() if k not in run_specific} == {
        k: v for k, v in before.items() if k not in run_specific
    }


def test_proposal_records_scan_tree_sha256(tmp_path: Path) -> None:
    repo = _employment_repo(tmp_path)
    assert _scan(tmp_path, repo, "--propose").exit_code == 0
    doc = load_proposal(repo / PROPOSAL_FILENAME)
    report = run_scan("prop-sys", "HEAD", repo, "customer support chatbot")
    assert report.source_tree_sha256
    assert doc["scan_tree_sha256"] == report.source_tree_sha256
    # The proposal file now sits in the tree and the value does not move.
    assert (repo / PROPOSAL_FILENAME).is_file()


def test_propose_with_legacy_exits_2_writes_nothing(tmp_path: Path) -> None:
    repo = _employment_repo(tmp_path)
    result = _scan(tmp_path, repo, "--propose", "--ai-legacy")
    assert result.exit_code == 2, result.output
    assert not (repo / PROPOSAL_FILENAME).exists()


def _propose(tmp_path: Path, repo: Path, *extra: str):
    """A `--propose` scan without the `--ai-model` that `_COMMON` carries."""
    return runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(_manifest(tmp_path)),
            "--repo-root",
            str(repo),
            "--no-emit-evidence",
            "--no-ocignore-bootstrap",
            "--propose",
            *extra,
        ],
    )


def _base_install(monkeypatch, tmp_path: Path, config: str | None = None) -> None:
    monkeypatch.setitem(sys.modules, "llama_cpp", None)
    cfg = tmp_path / "ai-config.yaml"
    if config is not None:
        cfg.write_text(config, encoding="utf-8")
    monkeypatch.setattr("opencomplai_ai.config._AI_CONFIG_FILE", cfg)


def test_propose_defaults_to_deterministic_backend(monkeypatch, tmp_path: Path) -> None:
    _base_install(monkeypatch, tmp_path)
    repo = _employment_repo(tmp_path)
    result = _propose(tmp_path, repo)
    assert result.exit_code == 0, result.output
    doc = load_proposal(repo / PROPOSAL_FILENAME)
    assert doc["ai_model_id"] == "codebert-onnx"
    assert doc["ai_backend"] == "deterministic"
    assert "Intent backend: codebert-onnx" in result.output


def test_propose_ai_model_flag_is_respected(monkeypatch, tmp_path: Path) -> None:
    _base_install(monkeypatch, tmp_path)
    import opencomplai_cli.main as cli_main

    seen: list[str | None] = []

    def preload(model_id):
        seen.append(model_id)
        return True

    monkeypatch.setattr(cli_main, "_preload_ai_model", preload)
    repo = _employment_repo(tmp_path)
    result = _propose(tmp_path, repo, "--ai-model", "qwen2.5-coder-0.5b")
    assert seen == ["qwen2.5-coder-0.5b"]
    assert result.exit_code == 2, result.output
    assert not (repo / PROPOSAL_FILENAME).exists()

    monkeypatch.undo()
    _base_install(monkeypatch, tmp_path)
    ok = _propose(tmp_path, repo, "--ai-model", "codebert-onnx")
    assert ok.exit_code == 0, ok.output
    assert load_proposal(repo / PROPOSAL_FILENAME)["ai_model_id"] == "codebert-onnx"


def test_propose_ignores_configured_default_model(monkeypatch, tmp_path: Path) -> None:
    _base_install(monkeypatch, tmp_path, "model_id: qwen2.5-coder-0.5b\n")
    repo = _employment_repo(tmp_path)
    result = _propose(tmp_path, repo)
    assert result.exit_code == 0, result.output
    assert load_proposal(repo / PROPOSAL_FILENAME)["ai_model_id"] == "codebert-onnx"
