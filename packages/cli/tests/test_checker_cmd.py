"""Tests for opencomplai checker CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()
FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "core"
    / "tests"
    / "fixtures"
    / "checker_golden"
)


def test_checker_answers_json_output(tmp_path: Path) -> None:
    fixture = json.loads(
        (FIXTURES / "06_high_risk_provider.json").read_text(encoding="utf-8")
    )
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps(fixture["session"]), encoding="utf-8")

    result = runner.invoke(
        app,
        ["checker", "--answers", str(answers_path), "--output", "json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["is_high_risk"] is True
    assert payload["effective_entity"] == "provider"


def test_checker_export_json(tmp_path: Path) -> None:
    fixture = json.loads(
        (FIXTURES / "01_auth_rep_only.json").read_text(encoding="utf-8")
    )
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps(fixture["session"]), encoding="utf-8")
    out = tmp_path / "result.json"

    result = runner.invoke(
        app,
        ["checker", "--answers", str(answers_path), "--export-json", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "authorised_representative" in [o["id"] for o in data["obligations"]]


def test_checker_web_default_url_points_to_docs() -> None:
    """--web with no env override must open docs.opencomplai.com, not the apex domain."""
    with patch("webbrowser.open") as mock_open:
        result = runner.invoke(app, ["checker", "--web"])
    assert result.exit_code == 0, result.stdout
    opened_url: str = mock_open.call_args[0][0]
    assert opened_url.startswith("https://docs.opencomplai.com/"), (
        f"Expected docs.opencomplai.com URL, got: {opened_url}"
    )
    assert "getting-started/eu-ai-act-checker" in opened_url


def test_checker_web_env_override_respected() -> None:
    """OPENCOMPLAI_DOCS_URL env var must override the default."""
    import os

    custom = "https://example.com/custom-checker/"
    with (
        patch("webbrowser.open") as mock_open,
        patch.dict(os.environ, {"OPENCOMPLAI_DOCS_URL": custom}),
    ):
        result = runner.invoke(app, ["checker", "--web"])
    assert result.exit_code == 0, result.stdout
    assert mock_open.call_args[0][0] == custom


def test_checker_web_local_serves_and_stops_via_page_button() -> None:
    """--web --local marks the URL for the in-page Stop control, and hitting
    the shutdown route it calls actually stops the blocked CLI process."""
    import threading
    import time
    import urllib.request

    opened_urls: list[str] = []
    result_holder: dict = {}

    def fake_open(url: str) -> bool:
        opened_urls.append(url)
        return True

    def run_cli() -> None:
        with patch("webbrowser.open", side_effect=fake_open):
            result_holder["result"] = runner.invoke(
                app, ["checker", "--web", "--local"]
            )

    thread = threading.Thread(target=run_cli)
    thread.start()
    try:
        deadline = time.time() + 5
        while not opened_urls and time.time() < deadline:
            time.sleep(0.05)
        assert opened_urls, "local server never opened a URL"
        local_url = opened_urls[0]
        assert "?local=1" in local_url, (
            "checker-widget UI relies on this marker to show its Stop control"
        )

        shutdown_url = local_url.split("?", 1)[0] + "__ococ_shutdown"
        with urllib.request.urlopen(shutdown_url, timeout=5) as resp:
            assert resp.status == 200
    finally:
        thread.join(timeout=5)

    assert not thread.is_alive(), "CLI did not stop after the shutdown route was hit"
    assert result_holder["result"].exit_code == 0, result_holder["result"].stdout


def _isolate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))


def _write_checker_manifest(tmp_path: Path, fixture_name: str) -> Path:
    fixture = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps(fixture["session"]), encoding="utf-8")
    manifest_path = tmp_path / "system-manifest.json"

    result = runner.invoke(
        app,
        [
            "checker",
            "--answers",
            str(answers_path),
            "--write-manifest",
            str(manifest_path),
            "--intended-purpose",
            "Summarises internal documents",
        ],
        input="doc-summariser\n",
    )
    assert result.exit_code == 0, result.output
    return manifest_path


def test_checker_write_manifest_keeps_purpose_and_records_verdict(
    tmp_path: Path, monkeypatch
) -> None:
    """The tier label belongs in checker_session.verdict: the EU rules
    keyword-match intended_purpose, so a label there classifies nothing."""
    _isolate(tmp_path, monkeypatch)
    manifest_path = _write_checker_manifest(tmp_path, "05_prohibited.json")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["system_id"] == "doc-summariser"
    assert data["intended_purpose"] == "Summarises internal documents"
    assert data["checker_session"]["verdict"] == "prohibited_practice"


def test_check_blocks_prohibited_checker_verdict(tmp_path: Path, monkeypatch) -> None:
    """A purpose the rules find harmless must not PASS a system the checker
    classified prohibited."""
    _isolate(tmp_path, monkeypatch)
    manifest_path = _write_checker_manifest(tmp_path, "05_prohibited.json")

    result = runner.invoke(app, ["check", "-m", str(manifest_path), "-o", "json"])
    assert result.exit_code == 3, result.output
    artifact = json.loads((tmp_path / "compliance-artifact.json").read_text())
    assert artifact["result"] == "policy_block"
    assert artifact["failed_controls"].count("EU_AIA_ART5_UNACCEPTABLE") == 1


def test_check_honours_legacy_verdict_in_intended_purpose(
    tmp_path: Path, monkeypatch
) -> None:
    """0.7.0 wrote the verdict into intended_purpose; check still fails on
    it and tells the user to put the real purpose there."""
    _isolate(tmp_path, monkeypatch)
    manifest_path = tmp_path / "system-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "system_id": "legacy-sys",
                "intended_purpose": "high_risk_ai_system",
                "compliance_target": "EU_AI_ACT",
                "high_risk_presumption": True,
                "commit_ref": "HEAD",
                "operator_role": "provider",
                "checker_session": {
                    "checker_version": "checker-2026-07-24",
                    "session_id": "legacy-session",
                    "completed_at": "2026-09-01T00:00:00+00:00",
                    "report_json_path": "",
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["check", "-m", str(manifest_path), "-o", "json"])
    assert result.exit_code == 1, result.output
    assert "WARN" in result.stderr
    assert "high_risk_ai_system" in result.stderr
    artifact = json.loads(result.stdout)
    assert artifact["result"] == "control_fail"
    assert "EU_AIA_ART6_HIGH_RISK" in artifact["failed_controls"]
