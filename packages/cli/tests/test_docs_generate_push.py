"""
Tests for DG-10's ``opencomplai docs generate --push/--no-push`` wiring
(``opencomplai_cli.main.docs_generate_cmd`` / ``_push_dossier_envelope``).

Forces the local-fallback path (no OPENCOMPLAI_API_URL set) so `docs
generate` actually reaches the branch that has the full AnnexIVDossier
object DG-10 pushes from -- same convention as
``test_docs_generate_wiring.py``. ``publish_dossier_envelope`` is mocked so
nothing here touches the network.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()

_SYSTEM_ID = "dg10-push-test"
_COMMIT_REF = "HEAD"

_VALID_ENV = {
    "OPENCOMPLAI_API_KEY": "ock_testkey",
    "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test/api/ingest",
}


def _invoke(output_dir: Path, extra_args: list[str], env: dict[str, str] | None = None):
    return runner.invoke(
        app,
        [
            "docs",
            "generate",
            "--system-id",
            _SYSTEM_ID,
            "--commit-ref",
            _COMMIT_REF,
            "--output-dir",
            str(output_dir),
            *extra_args,
        ],
        env=env,
    )


class TestNoPushDefault:
    def test_default_is_no_push_and_publish_never_called(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
        output_dir = tmp_path / "out"

        with patch("opencomplai_cli.publish.publish_dossier_envelope") as mock_publish:
            result = _invoke(output_dir, [])
        assert result.exit_code == 0, result.output
        mock_publish.assert_not_called()
        # The dossier itself is still written locally -- --no-push only
        # means "don't also push", not "don't generate".
        assert list(output_dir.glob("dossier_*.json"))

    def test_explicit_no_push_flag_never_calls_publish(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
        output_dir = tmp_path / "out"

        with patch("opencomplai_cli.publish.publish_dossier_envelope") as mock_publish:
            result = _invoke(output_dir, ["--no-push"], env=dict(_VALID_ENV))
        assert result.exit_code == 0, result.output
        mock_publish.assert_not_called()


class TestPushSuccess:
    def test_push_201_exits_0_and_calls_publish(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
        output_dir = tmp_path / "out"

        with patch(
            "opencomplai_cli.publish.publish_dossier_envelope",
            return_value=(201, {"outcome": "accepted", "content_hash": "abc"}),
        ) as mock_publish:
            result = _invoke(output_dir, ["--push"], env=dict(_VALID_ENV))
        assert result.exit_code == 0, result.output
        mock_publish.assert_called_once()

    def test_push_200_replay_exits_0(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
        output_dir = tmp_path / "out"

        with patch(
            "opencomplai_cli.publish.publish_dossier_envelope",
            return_value=(200, {"outcome": "replayed", "content_hash": "abc"}),
        ):
            result = _invoke(output_dir, ["--push"], env=dict(_VALID_ENV))
        assert result.exit_code == 0, result.output

    def test_push_envelope_shape_sent_to_publish(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
        output_dir = tmp_path / "out"

        with patch(
            "opencomplai_cli.publish.publish_dossier_envelope",
            return_value=(201, {"outcome": "accepted", "content_hash": "abc"}),
        ) as mock_publish:
            result = _invoke(output_dir, ["--push"], env=dict(_VALID_ENV))
        assert result.exit_code == 0, result.output

        base_url, token, envelope = mock_publish.call_args[0]
        assert base_url == "http://dash.test/api/ingest"
        assert token == "ock_testkey"
        assert envelope["system_id"] == _SYSTEM_ID
        assert envelope["signature"] == ""
        assert envelope["artifact"]["bundle_checksum"].startswith("sha256:")
        assert envelope["artifact"]["result"] == "generated"


class TestPushFailureExitCode:
    def test_push_4xx_exits_3(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
        output_dir = tmp_path / "out"

        with patch(
            "opencomplai_cli.publish.publish_dossier_envelope",
            return_value=(422, {"error_code": "SCHEMA_VIOLATION"}),
        ):
            result = _invoke(output_dir, ["--push"], env=dict(_VALID_ENV))
        assert result.exit_code == 3, result.output

    def test_push_401_exits_3(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
        output_dir = tmp_path / "out"

        with patch(
            "opencomplai_cli.publish.publish_dossier_envelope",
            return_value=(401, {"detail": "invalid or expired token"}),
        ):
            result = _invoke(output_dir, ["--push"], env=dict(_VALID_ENV))
        assert result.exit_code == 3, result.output

    def test_push_network_failure_exits_3(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
        output_dir = tmp_path / "out"

        with patch(
            "opencomplai_cli.publish.publish_dossier_envelope",
            return_value=(0, {"error": "connection refused"}),
        ):
            result = _invoke(output_dir, ["--push"], env=dict(_VALID_ENV))
        assert result.exit_code == 3, result.output

    def test_push_missing_env_vars_exits_3_without_network_call(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
        monkeypatch.delenv("OPENCOMPLAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENCOMPLAI_DASHBOARD_URL", raising=False)
        output_dir = tmp_path / "out"

        with patch("opencomplai_cli.publish.publish_dossier_envelope") as mock_publish:
            result = _invoke(output_dir, ["--push"])
        assert result.exit_code == 3, result.output
        mock_publish.assert_not_called()
