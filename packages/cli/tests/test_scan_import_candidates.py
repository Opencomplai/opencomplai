"""`scan --ai-intent`: import candidates are leads and never move an exit code."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from opencomplai_core import scan_engine
from opencomplai_core.models import SystemManifest
from typer.testing import CliRunner

runner = CliRunner()

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
            system_id="cand-sys", intended_purpose="customer support chatbot"
        ).model_dump_json(),
        encoding="utf-8",
    )
    return path


def _retinaface_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "face.py").write_text("import retinaface\n", encoding="utf-8")
    return repo


def _scan(tmp_path: Path, repo: Path):
    return runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(_manifest(tmp_path)),
            "--repo-root",
            str(repo),
            *_COMMON,
            "--ai-intent",
            "--fail-on",
            "major",
            "-o",
            "json",
        ],
    )


def test_fail_on_exit_code_unchanged_by_candidates(tmp_path, monkeypatch):
    repo = _retinaface_repo(tmp_path)

    with_candidates = _scan(tmp_path, repo)
    assert with_candidates.exit_code == 0, with_candidates.output
    payload = json.loads(with_candidates.stdout)["payload"]
    assert len(payload["eu_ai_scan"]["candidates"]) == 1

    monkeypatch.setattr(scan_engine, "find_import_candidates", lambda *a, **k: [])
    without = _scan(tmp_path, repo)
    assert without.exit_code == with_candidates.exit_code
    bare = json.loads(without.stdout)["payload"]
    assert bare["eu_ai_scan"]["candidates"] == []
    assert bare["severity"] == payload["severity"]
