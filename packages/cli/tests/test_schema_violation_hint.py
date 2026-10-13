"""A SCHEMA_VIOLATION push failure prints a generic upgrade hint."""

from __future__ import annotations

import json
import re
import urllib.error
from unittest.mock import MagicMock, patch

from opencomplai_cli.commands.push import (
    EXIT_PUBLISH_FAILED,
    run_push,
    run_push_dossier,
)
from opencomplai_cli.main import app
from opencomplai_cli.publish import SCHEMA_VIOLATION_HINT, schema_violation_hint
from typer.testing import CliRunner

runner = CliRunner()

_ENV = {
    "OPENCOMPLAI_API_KEY": "ock_testkey",
    "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test/api/ingest",
}
_ARTIFACT = {
    "install_id": "install-1",
    "system_id": "sys-1",
    "commit_ref": "a" * 40,
    "result": "pass",
    "failed_controls": [],
    "evidence_hashes": ["sha256:aaa"],
    "rationale_hash": "sha256:bbb",
    "duration_ms": 100,
    "pending_verifications_count": 0,
    "signature": None,
    "eval_summary": None,
    "scan_summary": None,
    "gap_report": None,
}
_DOSSIER = {
    "dossier_id": "doss-1",
    "system_id": "sys-1",
    "commit_ref": "a" * 40,
    "generated_at": "2026-05-18T18:46:11Z",
    "compliance_target": "EU_AI_ACT",
    "bundle_checksum": "sha256:" + "9" * 64,
    "signature": None,
    "signature_status": "unsigned",
}
_SV = {"error_code": "SCHEMA_VIOLATION"}


def _flat(text: str) -> str:
    return " ".join(text.split())


def _http_error(code: int, body: dict) -> urllib.error.HTTPError:
    exc = urllib.error.HTTPError(
        url="http://dash.test/x", code=code, msg="err", hdrs=None, fp=None
    )
    exc.read = MagicMock(return_value=json.dumps(body).encode("utf-8"))
    return exc


def _response(status: int, body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = json.dumps(body).encode("utf-8")
    return resp


def test_push_prints_hint_on_schema_violation(tmp_path, capsys):
    f = tmp_path / "compliance-artifact.json"
    f.write_text(json.dumps(_ARTIFACT), encoding="utf-8")
    with patch("urllib.request.urlopen", side_effect=_http_error(422, _SV)):
        code = run_push(f, env=dict(_ENV))
    assert code == EXIT_PUBLISH_FAILED
    assert SCHEMA_VIOLATION_HINT in _flat(capsys.readouterr().err)


def test_dossier_push_prints_hint(tmp_path, capsys):
    f = tmp_path / "dossier_x.json"
    f.write_text(json.dumps(_DOSSIER), encoding="utf-8")
    with patch("urllib.request.urlopen", side_effect=_http_error(422, _SV)):
        code = run_push_dossier(f, env=dict(_ENV))
    assert code == EXIT_PUBLISH_FAILED
    assert SCHEMA_VIOLATION_HINT in _flat(capsys.readouterr().err)


def test_docs_generate_push_prints_hint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    with patch(
        "opencomplai_cli.publish.publish_dossier_envelope", return_value=(422, _SV)
    ):
        result = runner.invoke(
            app,
            [
                "docs",
                "generate",
                "--system-id",
                "hint-test",
                "--commit-ref",
                "HEAD",
                "--output-dir",
                str(tmp_path / "out"),
                "--push",
            ],
            env=dict(_ENV),
        )
    assert result.exit_code == 3, result.output
    assert SCHEMA_VIOLATION_HINT in _flat(result.output)


def test_connector_warning_carries_hint():
    from opencomplai_cli.connectors.github_actions import _publish_to_dashboard

    env = {
        "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
        "OPENCOMPLAI_AUTH_TOKEN": "preset-token",
        "GITHUB_SHA": "c" * 40,
    }
    with (
        patch("urllib.request.urlopen") as mock_urlopen,
        patch("opencomplai_cli.connectors.github_actions._annotate") as annotate,
    ):
        mock_urlopen.return_value.__enter__.return_value = _response(422, _SV)
        _publish_to_dashboard({"system_id": "s1"}, env)
    msgs = [c.args[1] for c in annotate.call_args_list if c.args[0] == "warning"]
    assert any(SCHEMA_VIOLATION_HINT in m for m in msgs)


def test_gitlab_connector_warning_carries_hint(capsys):
    from opencomplai_cli.connectors.gitlab_ci import _publish_to_dashboard

    env = {
        "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
        "OPENCOMPLAI_AUTH_TOKEN": "preset-token",
        "CI_COMMIT_SHA": "e" * 40,
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _response(422, _SV)
        _publish_to_dashboard({"system_id": "s1"}, env)
    assert SCHEMA_VIOLATION_HINT in _flat(capsys.readouterr().err)


def test_no_hint_for_other_errors(tmp_path, capsys):
    f = tmp_path / "compliance-artifact.json"
    f.write_text(json.dumps(_ARTIFACT), encoding="utf-8")
    for status, body in (
        (422, {"error_code": "VALIDATION_ERROR"}),
        (401, {"error_code": "UNAUTHORIZED"}),
        (0, {"error": "x"}),
    ):
        with patch(
            "opencomplai_cli.commands.push.publish_scan_status",
            return_value=(status, body),
        ):
            assert run_push(f, env=dict(_ENV)) == EXIT_PUBLISH_FAILED
        assert "hint:" not in capsys.readouterr().err
        assert schema_violation_hint(body) == ""


def test_hint_text_is_generic():
    assert not re.search(
        r"\b(dashboard|hosted|saas|tenant|premium)\b", SCHEMA_VIOLATION_HINT, re.I
    )
