"""The default scan states what it covers: text notice and additive report field."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from opencomplai_cli import coverage_notice, main
from opencomplai_cli.main import app
from opencomplai_core.models import CorroborationReport, SystemManifest
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _setup(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    monkeypatch.delenv("OPENCOMPLAI_VAULT_URL", raising=False)
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setattr(main, "_SIGNING_KEY", key_dir / "signing.key")
    manifest = tmp_path / "system-manifest.json"
    manifest.write_text(
        SystemManifest(
            system_id="cov-sys",
            intended_purpose="customer support chatbot",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref="HEAD",
        ).model_dump_json(),
        encoding="utf-8",
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "face.py").write_text("import face_recognition\n", encoding="utf-8")
    return manifest, repo


def _scan(manifest: Path, repo: Path, *extra: str):
    return runner.invoke(
        app, ["scan", "--manifest", str(manifest), "--repo-root", str(repo), *extra]
    )


def _check(manifest: Path, repo: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--scan",
            *extra,
        ],
    )


def test_scan_text_states_default_coverage(tmp_path, monkeypatch):
    manifest, repo = _setup(tmp_path, monkeypatch)
    result = _scan(manifest, repo)
    assert result.exit_code == 0, result.output
    out = _flat(result.output)
    assert "What the default scan covers" in out
    assert "Annex III areas 3, 4, 5, 6, 7, 8 are not reached" in out
    assert "--ai-intent" in out
    assert "--propose" in out


def test_check_scan_text_states_default_coverage(tmp_path, monkeypatch):
    manifest, repo = _setup(tmp_path, monkeypatch)
    result = _check(manifest, repo)
    assert result.exit_code == 0, result.output
    assert "What the default scan covers" in _flat(result.output)


def test_check_without_scan_prints_no_notice(tmp_path, monkeypatch):
    manifest, repo = _setup(tmp_path, monkeypatch)
    result = runner.invoke(
        app, ["check", "--manifest", str(manifest), "--repo-root", str(repo)]
    )
    assert result.exit_code == 0, result.output
    assert "What the default scan covers" not in _flat(result.output)


def test_notice_absent_when_intent_analysis_ran():
    def _report(ran: bool) -> CorroborationReport:
        r = CorroborationReport.model_construct()
        r.default_scan_coverage = coverage_notice.default_scan_coverage(
            intent_analysis_ran=ran
        )
        return r

    assert coverage_notice.notice_lines(_report(True)) == []
    assert coverage_notice.notice_lines(_report(False))
    assert coverage_notice.notice_lines(CorroborationReport.model_construct()) == []


def test_scan_output_file_carries_field(tmp_path, monkeypatch):
    manifest, repo = _setup(tmp_path, monkeypatch)
    out_file = tmp_path / "out.json"
    result = _scan(manifest, repo, "--output-file", str(out_file))
    assert result.exit_code == 0, result.output
    data = json.loads(out_file.read_text(encoding="utf-8"))
    cov = data["default_scan_coverage"]
    assert cov["areas"]["1"] == "default_tokens"
    assert cov["intent_analysis_ran"] is False
    envelope = _scan(manifest, repo, "-o", "json")
    assert "default_scan_coverage" in envelope.output


def test_check_sidecar_has_field_artifact_lacks_it(tmp_path, monkeypatch):
    manifest, repo = _setup(tmp_path, monkeypatch)
    out_dir = tmp_path / "out"
    result = _check(manifest, repo, "--output-dir", str(out_dir))
    assert result.exit_code == 0, result.output
    sidecar = out_dir / "scan-report.json"
    assert "default_scan_coverage" in sidecar.read_text(encoding="utf-8")
    artifact_text = (out_dir / "compliance-artifact.json").read_text(encoding="utf-8")
    assert "default_scan_coverage" not in artifact_text
    digest = (
        "sha256:"
        + hashlib.sha256(sidecar.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    )
    assert digest in json.loads(artifact_text)["evidence_hashes"]


def test_exit_codes_unchanged_by_notice(tmp_path, monkeypatch):
    manifest, repo = _setup(tmp_path, monkeypatch)
    with_notice = (
        _scan(manifest, repo, "--fail-on", "major").exit_code,
        _check(manifest, repo).exit_code,
    )
    monkeypatch.setattr(coverage_notice, "notice_lines", lambda report: [])
    without = (
        _scan(manifest, repo, "--fail-on", "major").exit_code,
        _check(manifest, repo).exit_code,
    )
    assert with_notice == without


def test_report_hash_ignores_coverage_field(tmp_path, monkeypatch):
    manifest, repo = _setup(tmp_path, monkeypatch)
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    _scan(manifest, repo, "--output-file", str(out_a))
    real = coverage_notice.default_scan_coverage
    monkeypatch.setattr(
        coverage_notice,
        "default_scan_coverage",
        lambda **kw: {**real(**kw), "note": "different"},
    )
    _scan(manifest, repo, "--output-file", str(out_b))
    a = json.loads(out_a.read_text(encoding="utf-8"))
    b = json.loads(out_b.read_text(encoding="utf-8"))
    assert a["default_scan_coverage"] != b["default_scan_coverage"]
    assert a["report_hash"] == b["report_hash"]


def test_statuses_follow_signal_dictionary(monkeypatch):
    shipped = coverage_notice.default_scan_coverage(intent_analysis_ran=False)["areas"]
    assert shipped == {
        "1": "default_tokens",
        "2": "partial_tokens",
        **{str(a): "not_covered" for a in range(3, 9)},
    }
    real = coverage_notice.load_signals()
    monkeypatch.setattr(
        coverage_notice,
        "load_signals",
        lambda: {**real, "area_signals": {**real["area_signals"], "education": ["x"]}},
    )
    areas = coverage_notice.default_scan_coverage(intent_analysis_ran=False)["areas"]
    assert areas["3"] == "partial_tokens"
    monkeypatch.setattr(
        coverage_notice, "load_signals", lambda: {**real, "biometric": []}
    )
    areas = coverage_notice.default_scan_coverage(intent_analysis_ran=False)["areas"]
    assert areas["1"] == "not_covered"
