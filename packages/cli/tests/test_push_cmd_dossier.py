"""
Tests for DG-10's dossier-envelope push path:
``opencomplai_cli.commands.push.run_push_dossier`` and
``opencomplai push --kind {scan-status,dossier-envelope}`` routing in
``opencomplai_cli.main.push_cmd``.

Mirrors ``test_push_cmd.py``'s own conventions: ``run_push_dossier`` is
exercised directly with ``publish_dossier_envelope`` mocked so nothing here
touches the network.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from opencomplai_cli.commands.push import EXIT_OK, EXIT_PUBLISH_FAILED, run_push_dossier
from typer.testing import CliRunner

runner = CliRunner()

_VALID_ENV = {
    "OPENCOMPLAI_API_KEY": "ock_testkey",
    "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test/api/ingest",
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


class TestRunPushDossierArgAndEnvHandling:
    def test_missing_file_returns_publish_failed(self, tmp_path):
        code = run_push_dossier(tmp_path / "nope.json", env=dict(_VALID_ENV))
        assert code == EXIT_PUBLISH_FAILED

    def test_invalid_json_returns_publish_failed(self, tmp_path):
        bad = tmp_path / "dossier_x.json"
        bad.write_text("{not json", encoding="utf-8")
        code = run_push_dossier(bad, env=dict(_VALID_ENV))
        assert code == EXIT_PUBLISH_FAILED

    def test_json_array_not_object_returns_publish_failed(self, tmp_path):
        dossier_file = tmp_path / "dossier_x.json"
        dossier_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        code = run_push_dossier(dossier_file, env=dict(_VALID_ENV))
        assert code == EXIT_PUBLISH_FAILED

    def test_missing_api_key_returns_publish_failed(self, tmp_path):
        dossier_file = tmp_path / "dossier_x.json"
        dossier_file.write_text(json.dumps(_DOSSIER), encoding="utf-8")
        env = {"OPENCOMPLAI_DASHBOARD_URL": "http://dash.test"}
        code = run_push_dossier(dossier_file, env=env)
        assert code == EXIT_PUBLISH_FAILED

    def test_missing_dashboard_url_returns_publish_failed(self, tmp_path):
        dossier_file = tmp_path / "dossier_x.json"
        dossier_file.write_text(json.dumps(_DOSSIER), encoding="utf-8")
        env = {"OPENCOMPLAI_API_KEY": "ock_testkey"}
        code = run_push_dossier(dossier_file, env=env)
        assert code == EXIT_PUBLISH_FAILED


class TestRunPushDossierExitCodes:
    def test_201_returns_ok_and_prints_outcome(self, tmp_path, capsys):
        dossier_file = tmp_path / "dossier_x.json"
        dossier_file.write_text(json.dumps(_DOSSIER), encoding="utf-8")
        with patch(
            "opencomplai_cli.commands.push.publish_dossier_envelope",
            return_value=(201, {"outcome": "accepted", "content_hash": "deadbeef"}),
        ):
            code = run_push_dossier(dossier_file, env=dict(_VALID_ENV))
        assert code == EXIT_OK
        out = capsys.readouterr().out
        assert "accepted" in out
        assert "deadbeef" in out

    def test_200_replay_returns_ok(self, tmp_path):
        dossier_file = tmp_path / "dossier_x.json"
        dossier_file.write_text(json.dumps(_DOSSIER), encoding="utf-8")
        with patch(
            "opencomplai_cli.commands.push.publish_dossier_envelope",
            return_value=(200, {"outcome": "replayed", "content_hash": "abc"}),
        ):
            code = run_push_dossier(dossier_file, env=dict(_VALID_ENV))
        assert code == EXIT_OK

    def test_422_returns_publish_failed(self, tmp_path, capsys):
        dossier_file = tmp_path / "dossier_x.json"
        dossier_file.write_text(json.dumps(_DOSSIER), encoding="utf-8")
        with patch(
            "opencomplai_cli.commands.push.publish_dossier_envelope",
            return_value=(422, {"error_code": "SCHEMA_VIOLATION"}),
        ):
            code = run_push_dossier(dossier_file, env=dict(_VALID_ENV))
        assert code == EXIT_PUBLISH_FAILED
        assert "SCHEMA_VIOLATION" in capsys.readouterr().err

    def test_401_returns_publish_failed(self, tmp_path):
        dossier_file = tmp_path / "dossier_x.json"
        dossier_file.write_text(json.dumps(_DOSSIER), encoding="utf-8")
        with patch(
            "opencomplai_cli.commands.push.publish_dossier_envelope",
            return_value=(401, {"detail": "invalid or expired token"}),
        ):
            code = run_push_dossier(dossier_file, env=dict(_VALID_ENV))
        assert code == EXIT_PUBLISH_FAILED

    def test_network_failure_returns_publish_failed(self, tmp_path):
        dossier_file = tmp_path / "dossier_x.json"
        dossier_file.write_text(json.dumps(_DOSSIER), encoding="utf-8")
        with patch(
            "opencomplai_cli.commands.push.publish_dossier_envelope",
            return_value=(0, {"error": "connection refused"}),
        ):
            code = run_push_dossier(dossier_file, env=dict(_VALID_ENV))
        assert code == EXIT_PUBLISH_FAILED


class TestRunPushDossierEnvelopeShape:
    def test_signature_is_always_empty_string(self, tmp_path):
        """An AnnexIVDossier's own `signature` (when present) signs the
        bundle under a scheme unrelated to the envelope's G-5 byte-identity
        check -- must never be forwarded."""
        dossier_file = tmp_path / "dossier_x.json"
        signed = {**_DOSSIER, "signature": "base64sig==", "signature_status": "ed25519"}
        dossier_file.write_text(json.dumps(signed), encoding="utf-8")

        with patch(
            "opencomplai_cli.commands.push.publish_dossier_envelope",
            return_value=(201, {"outcome": "accepted", "content_hash": "abc"}),
        ) as mock_publish:
            run_push_dossier(dossier_file, env=dict(_VALID_ENV))

        _base_url, _token, envelope = mock_publish.call_args[0]
        assert envelope["signature"] == ""
        assert envelope["system_id"] == "sys-1"
        assert envelope["artifact"]["bundle_checksum"] == _DOSSIER["bundle_checksum"]

    def test_base_url_and_token_forwarded(self, tmp_path):
        dossier_file = tmp_path / "dossier_x.json"
        dossier_file.write_text(json.dumps(_DOSSIER), encoding="utf-8")

        with patch(
            "opencomplai_cli.commands.push.publish_dossier_envelope",
            return_value=(201, {"outcome": "accepted", "content_hash": "abc"}),
        ) as mock_publish:
            run_push_dossier(dossier_file, env=dict(_VALID_ENV))

        base_url, token, _envelope = mock_publish.call_args[0]
        assert base_url == "http://dash.test/api/ingest"
        assert token == "ock_testkey"


class TestPushCliKindRouting:
    def test_default_kind_is_scan_status(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "compliance-artifact.json").write_text(
            json.dumps(
                {"system_id": "sys-1", "commit_ref": "a" * 40, "result": "pass"}
            ),
            encoding="utf-8",
        )
        from opencomplai_cli.main import app

        with (
            patch(
                "opencomplai_cli.commands.push.publish_scan_status",
                return_value=(201, {"outcome": "accepted", "content_hash": "abc"}),
            ) as mock_scan,
            patch(
                "opencomplai_cli.commands.push.publish_dossier_envelope"
            ) as mock_dossier,
        ):
            result = runner.invoke(app, ["push"], env=dict(_VALID_ENV))
        assert result.exit_code == 0
        mock_scan.assert_called_once()
        mock_dossier.assert_not_called()

    def test_kind_dossier_envelope_routes_to_run_push_dossier(self, tmp_path):
        custom = tmp_path / "dossier_x.json"
        custom.write_text(json.dumps(_DOSSIER), encoding="utf-8")
        from opencomplai_cli.main import app

        with (
            patch(
                "opencomplai_cli.commands.push.publish_dossier_envelope",
                return_value=(201, {"outcome": "accepted", "content_hash": "abc"}),
            ) as mock_dossier,
            patch("opencomplai_cli.commands.push.publish_scan_status") as mock_scan,
        ):
            result = runner.invoke(
                app,
                ["push", str(custom), "--kind", "dossier-envelope"],
                env=dict(_VALID_ENV),
            )
        assert result.exit_code == 0, result.output
        mock_dossier.assert_called_once()
        mock_scan.assert_not_called()

    def test_kind_dossier_envelope_finds_latest_dossier_file_in_cwd(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dossier_older.json").write_text(
            json.dumps(_DOSSIER), encoding="utf-8"
        )
        newest = tmp_path / "dossier_newest.json"
        newest.write_text(
            json.dumps({**_DOSSIER, "dossier_id": "doss-2"}), encoding="utf-8"
        )
        import os
        import time

        # Ensure a distinct, later mtime on the "newest" file regardless of
        # filesystem timestamp resolution.
        now = time.time()
        os.utime(tmp_path / "dossier_older.json", (now - 10, now - 10))
        os.utime(newest, (now, now))

        from opencomplai_cli.main import app

        with patch(
            "opencomplai_cli.commands.push.publish_dossier_envelope",
            return_value=(201, {"outcome": "accepted", "content_hash": "abc"}),
        ) as mock_dossier:
            result = runner.invoke(
                app, ["push", "--kind", "dossier-envelope"], env=dict(_VALID_ENV)
            )
        assert result.exit_code == 0, result.output
        mock_dossier.assert_called_once()

    def test_kind_dossier_envelope_no_file_found_exits_3(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from opencomplai_cli.main import app

        result = runner.invoke(
            app, ["push", "--kind", "dossier-envelope"], env=dict(_VALID_ENV)
        )
        assert result.exit_code == 3

    def test_kind_dossier_envelope_cli_exits_3_on_publish_failure(self, tmp_path):
        custom = tmp_path / "dossier_x.json"
        custom.write_text(json.dumps(_DOSSIER), encoding="utf-8")
        from opencomplai_cli.main import app

        with patch(
            "opencomplai_cli.commands.push.publish_dossier_envelope",
            return_value=(422, {"error_code": "SCHEMA_VIOLATION"}),
        ):
            result = runner.invoke(
                app,
                ["push", str(custom), "--kind", "dossier-envelope"],
                env=dict(_VALID_ENV),
            )
        assert result.exit_code == 3
