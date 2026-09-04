"""
Tests for C1.5 — GitHub Actions and GitLab CI connectors.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# GitHub Actions connector tests
# ---------------------------------------------------------------------------


class TestGitHubActionsConnector:
    def test_parse_artifact_result_from_stdout(self):
        from opencomplai_cli.connectors.github_actions import _parse_artifact_result

        stdout = 'Some preamble\n{"result": "pass", "system_id": "s1", "content_hash": "abc"}\nTrailing'
        result = _parse_artifact_result(stdout)
        assert result is not None
        assert result["result"] == "pass"

    def test_parse_artifact_result_no_match(self):
        from opencomplai_cli.connectors.github_actions import _parse_artifact_result

        result = _parse_artifact_result("no json here")
        assert result is None

    def test_failed_controls_summary(self):
        from opencomplai_cli.connectors.github_actions import _failed_controls_summary

        artifact = {"failed_controls": ["ctrl-a", "ctrl-b", "ctrl-c"]}
        summary = _failed_controls_summary(artifact)
        assert "ctrl-a" in summary

    def test_failed_controls_summary_empty(self):
        from opencomplai_cli.connectors.github_actions import _failed_controls_summary

        assert _failed_controls_summary(None) == "unknown"
        # {} has no failed_controls key — same as None path.
        assert _failed_controls_summary({}) == "unknown"
        assert _failed_controls_summary({"failed_controls": []}) == "see output"

    def test_run_connector_control_fail_returns_1(self, tmp_path, monkeypatch):
        from opencomplai_cli.connectors.github_actions import run_connector

        # Isolate cwd -- run_connector now prefers a disk
        # compliance-artifact.json (F5a) over the stdout parse, and this
        # test wants to exercise the stdout-parse path specifically (no
        # disk artifact present), not whatever real file sits in the repo
        # root pytest itself was invoked from.
        monkeypatch.chdir(tmp_path)
        artifact = json.dumps(
            {
                "result": "control_fail",
                "system_id": "sys1",
                "failed_controls": ["ctrl-x"],
                "content_hash": "a" * 64,
            }
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=artifact + "\n",
                stderr="",
                returncode=0,
            )
            code = run_connector(env={"GITHUB_ACTIONS": "true"})

        assert code == 1

    def test_run_connector_pass_returns_0(self, tmp_path, monkeypatch):
        from opencomplai_cli.connectors.github_actions import run_connector

        monkeypatch.chdir(tmp_path)  # see isolation note above
        artifact = json.dumps(
            {
                "result": "pass",
                "system_id": "sys1",
                "content_hash": "a" * 64,
            }
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=artifact + "\n", stderr="", returncode=0
            )
            code = run_connector(env={})

        assert code == 0

    def test_run_connector_missing_binary_returns_2(self):
        from opencomplai_cli.connectors.github_actions import run_connector

        with patch("subprocess.run", side_effect=FileNotFoundError):
            code = run_connector(env={})

        assert code == 2

    def test_exit_code_propagation_trap_detected(self, tmp_path, monkeypatch, capsys):
        """FINDING 48.8: trap_detected is a build failure (Article 25
        deployment freeze) and must exit 4 with an error annotation, not
        pass silently through exit 0."""
        from opencomplai_cli.connectors.github_actions import run_connector

        monkeypatch.chdir(tmp_path)  # see isolation note above
        artifact = json.dumps(
            {"result": "trap_detected", "system_id": "s", "content_hash": "b" * 64}
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=0)
            code = run_connector(env={})

        assert code == 4
        assert "::error::" in capsys.readouterr().out

    def test_exit_code_propagation_policy_block(self, tmp_path, monkeypatch, capsys):
        """FINDING 48.8: policy_block (prohibited/Article 5 system) must fail
        the build (exit 3) with an error annotation, not the `notice` a
        passing/degraded result gets."""
        from opencomplai_cli.connectors.github_actions import run_connector

        monkeypatch.chdir(tmp_path)
        artifact = json.dumps(
            {"result": "policy_block", "system_id": "s", "content_hash": "c" * 64}
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=0)
            code = run_connector(env={})

        assert code == 3
        assert "::error::" in capsys.readouterr().out

    def test_exit_code_propagation_validation_fail(self, tmp_path, monkeypatch, capsys):
        """FINDING 48.8: validation_fail (manifest/input validation error)
        must fail the build (exit 2) with an error annotation."""
        from opencomplai_cli.connectors.github_actions import run_connector

        monkeypatch.chdir(tmp_path)
        artifact = json.dumps(
            {"result": "validation_fail", "system_id": "s", "content_hash": "d" * 64}
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=2)
            code = run_connector(env={})

        assert code == 2
        assert "::error::" in capsys.readouterr().out

    def test_set_output_written_to_file(self, tmp_path):
        from opencomplai_cli.connectors.github_actions import _set_output

        output_file = tmp_path / "outputs"
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            _set_output("result", "pass")

        content = output_file.read_text()
        assert "result=pass" in content

    def test_run_connector_uses_disk_artifact_when_stdout_is_indent_formatted(
        self, tmp_path, monkeypatch
    ):
        """Real `opencomplai check --sign` output (no `-o json`) is Rich's
        indent=2 multi-line JSON -- `_parse_artifact_result`'s line-scanner
        never matches it (the first line is a lone "{"), so before this fix
        `_publish_to_dashboard` never even saw a `result`. `check --sign`
        still writes compliance-artifact.json to disk regardless of
        --output; reading that from the connector's own cwd (the same cwd
        the check subprocess inherited) is what actually lets a real CI run
        propagate its result."""
        from opencomplai_cli.connectors.github_actions import run_connector

        monkeypatch.chdir(tmp_path)
        disk_artifact = {
            "result": "control_fail",
            "system_id": "disk-sys",
            "failed_controls": ["ctrl-x"],
            "content_hash": "a" * 64,
        }
        (tmp_path / "compliance-artifact.json").write_text(
            json.dumps(disk_artifact, indent=2), encoding="utf-8"
        )
        # The real console.print_json shape -- never a single-line object.
        indent_stdout = json.dumps(disk_artifact, indent=2)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=indent_stdout, stderr="", returncode=0
            )
            code = run_connector(env={"GITHUB_ACTIONS": "true"})

        # control_fail from the disk artifact must propagate to exit 1 --
        # with the old stdout-only parse this would come back 0 (no
        # artifact ever matched, so nothing ever failed the build).
        assert code == 1

    def _mock_urlopen_success(
        self,
        mock_urlopen,
        *,
        status=201,
        body=b'{"outcome": "accepted", "content_hash": "abc"}',
    ):
        response = MagicMock()
        response.status = status
        response.read.return_value = body
        mock_urlopen.return_value.__enter__.return_value = response
        return response

    def test_publish_uses_operator_set_token_without_acquiring_one(self):
        from opencomplai_cli.connectors.github_actions import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_AUTH_TOKEN": "preset-token",
            "OPENCOMPLAI_CLIENT_ID": "should-not-be-used",
            "OPENCOMPLAI_CLIENT_SECRET": "should-not-be-used",
            "OPENCOMPLAI_TOKEN_ENDPOINT": "http://idp.test/token",
            "GITHUB_SHA": "a" * 40,
        }
        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch("opencomplai_cli.oidc_client.acquire_token") as mock_acquire,
        ):
            self._mock_urlopen_success(mock_urlopen)
            _publish_to_dashboard({"system_id": "s1", "signature": "sig"}, env)
        mock_acquire.assert_not_called()
        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.get_header("Authorization") == "Bearer preset-token"

    def test_publish_shapes_artifact_through_the_shared_mapper(self):
        """G-4: the raw artifact 422s against ingest's schema (additionalProperties:
        false, missing policy_bundle_version/timestamp, commit_ref too short) --
        the connector must send it through prepare_scan_status_artifact first, and
        must still carry install_id at the envelope level (this is the
        JWT/OIDC-authed path, which keeps the pre-CORE-3 envelope contract).

        G-5: the embedded "sig" signature was computed over the artifact
        BEFORE mapping, and this artifact's mapping mutates it (adds
        policy_bundle_version/timestamp, resolves commit_ref) -- so per
        publish.envelope_signature the forwarded signature must be "",
        never the stale "sig" (which would deterministically fail
        SIGNATURE_INVALID on the dashboard side)."""
        from opencomplai_cli.connectors.github_actions import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_AUTH_TOKEN": "preset-token",
            "OPENCOMPLAI_INSTALL_ID": "install-123",
            "GITHUB_SHA": "b" * 40,
        }
        artifact = {
            "system_id": "s1",
            "commit_ref": "HEAD",
            "result": "pass",
            "evidence_hashes": ["sha256:aaa"],
            "rationale_hash": "sha256:bbb",
            "signature": "sig",
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            self._mock_urlopen_success(mock_urlopen)
            _publish_to_dashboard(artifact, env)

        sent_request = mock_urlopen.call_args[0][0]
        sent_body = json.loads(sent_request.data)
        assert sent_body["install_id"] == "install-123"
        assert sent_body["signature"] == ""
        sent_artifact = sent_body["artifact"]
        # Passed through untouched.
        assert sent_artifact["evidence_hashes"] == ["sha256:aaa"]
        assert sent_artifact["rationale_hash"] == "sha256:bbb"
        # Synthesized because the OSS artifact never carries them.
        assert sent_artifact["policy_bundle_version"].startswith("cli-")
        assert sent_artifact["timestamp"]
        # "HEAD" is unusable (4 chars, minLength: 7) -- resolved via GITHUB_SHA.
        assert sent_artifact["commit_ref"] == "b" * 40

    def test_publish_legacy_path_unsigned_artifact_signature_is_empty_not_null(self):
        """Bug fix: prepared.get("signature", "") used to yield JSON `null`
        for an unsigned OSS artifact whose dict carries an explicit
        `"signature": None` key (the .get default never applies when the
        key IS present, just set to None) -- envelope_signature fixes
        this."""
        from opencomplai_cli.connectors.github_actions import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_AUTH_TOKEN": "preset-token",
            "GITHUB_SHA": "a" * 40,
        }
        artifact = {
            "system_id": "s1",
            "commit_ref": "a" * 40,
            "result": "pass",
            "signature": None,
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            self._mock_urlopen_success(mock_urlopen)
            _publish_to_dashboard(artifact, env)

        sent_body = json.loads(mock_urlopen.call_args[0][0].data)
        assert sent_body["signature"] == ""

    def test_publish_uses_api_key_when_set_no_install_id_no_oidc(self):
        """GO-LIVE CORE-4: OPENCOMPLAI_API_KEY (the ock_ key-authed path)
        takes priority over the legacy bearer-token override and OIDC
        entirely, and sends the key-authed envelope shape -- no install_id
        key at all."""
        from opencomplai_cli.connectors.github_actions import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_API_KEY": "ock_testkey",
            "OPENCOMPLAI_AUTH_TOKEN": "should-not-be-used",
            "OPENCOMPLAI_CLIENT_ID": "should-not-be-used",
            "OPENCOMPLAI_CLIENT_SECRET": "should-not-be-used",
            "OPENCOMPLAI_TOKEN_ENDPOINT": "http://idp.test/token",
            "GITHUB_SHA": "a" * 40,
        }
        artifact = {"system_id": "s1", "commit_ref": "a" * 40, "result": "pass"}
        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch("opencomplai_cli.oidc_client.acquire_token") as mock_acquire,
        ):
            self._mock_urlopen_success(mock_urlopen)
            _publish_to_dashboard(artifact, env)

        mock_acquire.assert_not_called()
        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.get_header("Authorization") == "Bearer ock_testkey"
        sent_body = json.loads(sent_request.data)
        assert "install_id" not in sent_body

    def test_publish_warns_on_non_2xx_response(self):
        from opencomplai_cli.connectors.github_actions import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_AUTH_TOKEN": "preset-token",
            "GITHUB_SHA": "c" * 40,
        }
        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch(
                "opencomplai_cli.connectors.github_actions._annotate"
            ) as mock_annotate,
        ):
            self._mock_urlopen_success(
                mock_urlopen, status=422, body=b'{"error_code": "SCHEMA_VIOLATION"}'
            )
            _publish_to_dashboard({"system_id": "s1"}, env)
        assert any(call.args[0] == "warning" for call in mock_annotate.call_args_list)

    def test_publish_acquires_token_via_client_credentials_when_auth_token_unset(self):
        from opencomplai_cli.connectors.github_actions import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_CLIENT_ID": "client-1",
            "OPENCOMPLAI_CLIENT_SECRET": "secret-1",
            "OPENCOMPLAI_TOKEN_ENDPOINT": "http://idp.test/token",
            "GITHUB_SHA": "a" * 40,
        }
        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch(
                "opencomplai_cli.oidc_client.acquire_token",
                return_value=("acquired-jwt", 3600),
            ) as mock_acquire,
        ):
            self._mock_urlopen_success(mock_urlopen)
            _publish_to_dashboard({"system_id": "s1", "signature": "sig"}, env)
        mock_acquire.assert_called_once_with(
            "http://idp.test/token", "client-1", "secret-1"
        )
        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.get_header("Authorization") == "Bearer acquired-jwt"

    def test_publish_skips_silently_when_neither_token_nor_credentials_set(self):
        from opencomplai_cli.connectors.github_actions import _publish_to_dashboard

        env = {"OPENCOMPLAI_DASHBOARD_URL": "http://dash.test"}
        with patch("urllib.request.urlopen") as mock_urlopen:
            _publish_to_dashboard({"system_id": "s1", "signature": "sig"}, env)
        mock_urlopen.assert_not_called()

    def test_publish_annotates_warning_when_acquisition_fails(self):
        from opencomplai_cli.connectors.github_actions import _publish_to_dashboard
        from opencomplai_cli.oidc_client import OidcTokenError

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_CLIENT_ID": "client-1",
            "OPENCOMPLAI_CLIENT_SECRET": "secret-1",
            "OPENCOMPLAI_TOKEN_ENDPOINT": "http://idp.test/token",
        }
        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch(
                "opencomplai_cli.oidc_client.acquire_token",
                side_effect=OidcTokenError("token endpoint returned 401"),
            ),
            patch(
                "opencomplai_cli.connectors.github_actions._annotate"
            ) as mock_annotate,
        ):
            _publish_to_dashboard({"system_id": "s1", "signature": "sig"}, env)
        mock_urlopen.assert_not_called()  # no token acquired -> publish skipped
        assert any(call.args[0] == "warning" for call in mock_annotate.call_args_list)


# ---------------------------------------------------------------------------
# GitLab CI connector tests
# ---------------------------------------------------------------------------


class TestGitLabCIConnector:
    def test_parse_artifact_result(self):
        from opencomplai_cli.connectors.gitlab_ci import _parse_artifact_result

        stdout = '{"result": "control_fail", "failed_controls": ["c1"]}'
        result = _parse_artifact_result(stdout)
        assert result is not None
        assert result["result"] == "control_fail"

    def test_build_junit_xml_pass(self):
        from opencomplai_cli.connectors.gitlab_ci import _build_junit_xml

        artifact = {"result": "pass", "system_id": "s1"}
        xml = _build_junit_xml(artifact, "")
        assert "testsuite" in xml
        assert "testcase" in xml
        assert "failure" not in xml

    def test_build_junit_xml_control_fail(self):
        from opencomplai_cli.connectors.gitlab_ci import _build_junit_xml

        artifact = {"result": "control_fail", "failed_controls": ["ctrl-a"]}
        xml = _build_junit_xml(artifact, "some output")
        assert "failure" in xml
        assert "ctrl-a" in xml

    def test_run_connector_control_fail_returns_1(self, tmp_path, monkeypatch):
        from opencomplai_cli.connectors.gitlab_ci import run_connector

        # Isolate cwd -- see the GitHub Actions connector's identical note.
        monkeypatch.chdir(tmp_path)
        artifact = json.dumps({"result": "control_fail", "failed_controls": ["c1"]})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=0)
            code = run_connector(env={}, junit_path=os.devnull)

        assert code == 1

    def test_run_connector_pass_returns_0(self, tmp_path, monkeypatch):
        from opencomplai_cli.connectors.gitlab_ci import run_connector

        monkeypatch.chdir(tmp_path)  # see isolation note above
        artifact = json.dumps({"result": "pass", "system_id": "s"})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=0)
            code = run_connector(env={}, junit_path=os.devnull)

        assert code == 0

    def test_run_connector_trap_detected_returns_4(self, tmp_path, monkeypatch, capsys):
        """FINDING 48.8: trap_detected is a pipeline failure (Article 25
        deployment freeze) and must exit 4, not pass silently through 0."""
        from opencomplai_cli.connectors.gitlab_ci import run_connector

        monkeypatch.chdir(tmp_path)
        artifact = json.dumps({"result": "trap_detected", "system_id": "s"})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=0)
            code = run_connector(env={}, junit_path=os.devnull)

        assert code == 4
        assert "trap_detected" in capsys.readouterr().err

    def test_run_connector_policy_block_returns_3(self, tmp_path, monkeypatch, capsys):
        """FINDING 48.8: policy_block (prohibited/Article 5 system) must
        fail the pipeline (exit 3)."""
        from opencomplai_cli.connectors.gitlab_ci import run_connector

        monkeypatch.chdir(tmp_path)
        artifact = json.dumps({"result": "policy_block", "system_id": "s"})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=0)
            code = run_connector(env={}, junit_path=os.devnull)

        assert code == 3
        assert "policy_block" in capsys.readouterr().err

    def test_run_connector_validation_fail_returns_2(
        self, tmp_path, monkeypatch, capsys
    ):
        """FINDING 48.8: validation_fail (manifest/input validation error)
        must fail the pipeline (exit 2)."""
        from opencomplai_cli.connectors.gitlab_ci import run_connector

        monkeypatch.chdir(tmp_path)
        artifact = json.dumps({"result": "validation_fail", "system_id": "s"})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=2)
            code = run_connector(env={}, junit_path=os.devnull)

        assert code == 2
        assert "validation_fail" in capsys.readouterr().err

    def test_build_junit_xml_trap_detected_is_a_failure(self):
        """FINDING 48.8: trap_detected now fails the build, so the JUnit
        case must report it as a <failure>, not a <system-out> that would
        leave the test report green while the pipeline exit code is 4."""
        from opencomplai_cli.connectors.gitlab_ci import _build_junit_xml

        artifact = {"result": "trap_detected", "system_id": "s"}
        xml = _build_junit_xml(artifact, "some output")
        assert "<failure" in xml
        assert "trap_detected" in xml

    def test_run_connector_missing_binary_returns_2(self):
        from opencomplai_cli.connectors.gitlab_ci import run_connector

        with patch("subprocess.run", side_effect=FileNotFoundError):
            code = run_connector(env={}, junit_path=os.devnull)

        assert code == 2

    def test_write_dotenv(self, tmp_path):
        from opencomplai_cli.connectors.gitlab_ci import _write_dotenv

        path = str(tmp_path / "opencomplai.env")
        _write_dotenv(path, {"result": "pass", "system_id": "s", "content_hash": "abc"})
        content = open(path).read()
        assert "OPENCOMPLAI_RESULT=pass" in content
        assert "OPENCOMPLAI_SYSTEM_ID=s" in content

    def test_junit_written_to_file(self, tmp_path, monkeypatch):
        from opencomplai_cli.connectors.gitlab_ci import run_connector

        monkeypatch.chdir(tmp_path)  # see isolation note above
        junit_path = str(tmp_path / "report.xml")
        artifact = json.dumps({"result": "pass", "system_id": "s"})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=0)
            run_connector(env={}, junit_path=junit_path)

        content = open(junit_path).read()
        assert "testsuite" in content

    def test_run_connector_uses_disk_artifact_when_stdout_is_indent_formatted(
        self, tmp_path, monkeypatch
    ):
        """Same real-world trap as the GitHub Actions connector: real
        `check --sign` stdout is Rich's indent=2 multi-line JSON, which
        `_parse_artifact_result` never matches -- the disk artifact must be
        preferred."""
        from opencomplai_cli.connectors.gitlab_ci import run_connector

        monkeypatch.chdir(tmp_path)
        disk_artifact = {
            "result": "control_fail",
            "system_id": "disk-sys",
            "failed_controls": ["ctrl-x"],
        }
        (tmp_path / "compliance-artifact.json").write_text(
            json.dumps(disk_artifact, indent=2), encoding="utf-8"
        )
        indent_stdout = json.dumps(disk_artifact, indent=2)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=indent_stdout, stderr="", returncode=0
            )
            code = run_connector(env={}, junit_path=os.devnull)

        assert code == 1

    def _mock_urlopen_success(
        self,
        mock_urlopen,
        *,
        status=201,
        body=b'{"outcome": "accepted", "content_hash": "abc"}',
    ):
        response = MagicMock()
        response.status = status
        response.read.return_value = body
        mock_urlopen.return_value.__enter__.return_value = response
        return response

    def test_publish_uses_operator_set_token_without_acquiring_one(self):
        from opencomplai_cli.connectors.gitlab_ci import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_AUTH_TOKEN": "preset-token",
            "OPENCOMPLAI_CLIENT_ID": "should-not-be-used",
            "OPENCOMPLAI_CLIENT_SECRET": "should-not-be-used",
            "OPENCOMPLAI_TOKEN_ENDPOINT": "http://idp.test/token",
            "CI_COMMIT_SHA": "a" * 40,
        }
        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch("opencomplai_cli.oidc_client.acquire_token") as mock_acquire,
        ):
            self._mock_urlopen_success(mock_urlopen)
            _publish_to_dashboard({"system_id": "s1", "signature": "sig"}, env)
        mock_acquire.assert_not_called()
        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.get_header("Authorization") == "Bearer preset-token"

    def test_publish_shapes_artifact_through_the_shared_mapper(self):
        """G-4: same shaping contract as the GitHub Actions connector (both go
        through opencomplai_cli.publish.prepare_scan_status_artifact).

        G-5: this artifact's mapping mutates it (policy_bundle_version/
        timestamp added, commit_ref resolved from "HEAD"), so per
        publish.envelope_signature the embedded "sig" -- signed over the
        pre-mapping bytes -- must NOT be forwarded; it would
        deterministically fail SIGNATURE_INVALID on the dashboard side."""
        from opencomplai_cli.connectors.gitlab_ci import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_AUTH_TOKEN": "preset-token",
            "OPENCOMPLAI_INSTALL_ID": "install-456",
            "CI_COMMIT_SHA": "d" * 40,
        }
        artifact = {
            "system_id": "s1",
            "commit_ref": "HEAD",
            "result": "pass",
            "scan_summary": {
                "scan_id": "scan1",
                "scanner_version": "1.0.0",
                "severity": "none",
                "report_hash": "sha256:ccc",
            },
            "signature": "sig",
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            self._mock_urlopen_success(mock_urlopen)
            _publish_to_dashboard(artifact, env)

        sent_request = mock_urlopen.call_args[0][0]
        sent_body = json.loads(sent_request.data)
        assert sent_body["install_id"] == "install-456"
        assert sent_body["signature"] == ""
        sent_artifact = sent_body["artifact"]
        assert sent_artifact["scan_summary"]["scan_id"] == "scan1"
        assert sent_artifact["policy_bundle_version"].startswith("cli-")
        assert sent_artifact["timestamp"]
        assert sent_artifact["commit_ref"] == "d" * 40

    def test_publish_legacy_path_unsigned_artifact_signature_is_empty_not_null(self):
        """Same bug fix as the GitHub Actions connector: an explicit
        `"signature": None` key must send JSON `""`, not `null`."""
        from opencomplai_cli.connectors.gitlab_ci import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_AUTH_TOKEN": "preset-token",
            "CI_COMMIT_SHA": "a" * 40,
        }
        artifact = {
            "system_id": "s1",
            "commit_ref": "a" * 40,
            "result": "pass",
            "signature": None,
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            self._mock_urlopen_success(mock_urlopen)
            _publish_to_dashboard(artifact, env)

        sent_body = json.loads(mock_urlopen.call_args[0][0].data)
        assert sent_body["signature"] == ""

    def test_publish_uses_api_key_when_set_no_install_id_no_oidc(self):
        """GO-LIVE CORE-4: OPENCOMPLAI_API_KEY takes priority over
        the legacy bearer-token override and OIDC entirely, sending the
        key-authed envelope shape -- no install_id key at all."""
        from opencomplai_cli.connectors.gitlab_ci import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_API_KEY": "ock_testkey",
            "OPENCOMPLAI_AUTH_TOKEN": "should-not-be-used",
            "OPENCOMPLAI_CLIENT_ID": "should-not-be-used",
            "OPENCOMPLAI_CLIENT_SECRET": "should-not-be-used",
            "OPENCOMPLAI_TOKEN_ENDPOINT": "http://idp.test/token",
            "CI_COMMIT_SHA": "a" * 40,
        }
        artifact = {"system_id": "s1", "commit_ref": "a" * 40, "result": "pass"}
        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch("opencomplai_cli.oidc_client.acquire_token") as mock_acquire,
        ):
            self._mock_urlopen_success(mock_urlopen)
            _publish_to_dashboard(artifact, env)

        mock_acquire.assert_not_called()
        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.get_header("Authorization") == "Bearer ock_testkey"
        sent_body = json.loads(sent_request.data)
        assert "install_id" not in sent_body

    def test_publish_warns_on_non_2xx_response(self, capsys):
        from opencomplai_cli.connectors.gitlab_ci import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_AUTH_TOKEN": "preset-token",
            "CI_COMMIT_SHA": "e" * 40,
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            self._mock_urlopen_success(
                mock_urlopen, status=422, body=b'{"error_code": "SCHEMA_VIOLATION"}'
            )
            _publish_to_dashboard({"system_id": "s1"}, env)
        assert "dashboard publish failed" in capsys.readouterr().err

    def test_publish_acquires_token_via_client_credentials_when_auth_token_unset(self):
        from opencomplai_cli.connectors.gitlab_ci import _publish_to_dashboard

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_CLIENT_ID": "client-1",
            "OPENCOMPLAI_CLIENT_SECRET": "secret-1",
            "OPENCOMPLAI_TOKEN_ENDPOINT": "http://idp.test/token",
            "CI_COMMIT_SHA": "a" * 40,
        }
        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch(
                "opencomplai_cli.oidc_client.acquire_token",
                return_value=("acquired-jwt", 3600),
            ) as mock_acquire,
        ):
            self._mock_urlopen_success(mock_urlopen)
            _publish_to_dashboard({"system_id": "s1", "signature": "sig"}, env)
        mock_acquire.assert_called_once_with(
            "http://idp.test/token", "client-1", "secret-1"
        )
        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.get_header("Authorization") == "Bearer acquired-jwt"

    def test_publish_skips_silently_when_neither_token_nor_credentials_set(self):
        from opencomplai_cli.connectors.gitlab_ci import _publish_to_dashboard

        env = {"OPENCOMPLAI_DASHBOARD_URL": "http://dash.test"}
        with patch("urllib.request.urlopen") as mock_urlopen:
            _publish_to_dashboard({"system_id": "s1", "signature": "sig"}, env)
        mock_urlopen.assert_not_called()

    def test_publish_prints_warning_when_acquisition_fails(self, capsys):
        from opencomplai_cli.connectors.gitlab_ci import _publish_to_dashboard
        from opencomplai_cli.oidc_client import OidcTokenError

        env = {
            "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test",
            "OPENCOMPLAI_CLIENT_ID": "client-1",
            "OPENCOMPLAI_CLIENT_SECRET": "secret-1",
            "OPENCOMPLAI_TOKEN_ENDPOINT": "http://idp.test/token",
        }
        with (
            patch("urllib.request.urlopen") as mock_urlopen,
            patch(
                "opencomplai_cli.oidc_client.acquire_token",
                side_effect=OidcTokenError("token endpoint returned 401"),
            ),
        ):
            _publish_to_dashboard({"system_id": "s1", "signature": "sig"}, env)
        mock_urlopen.assert_not_called()  # no token acquired -> publish skipped
        assert "OIDC token acquisition failed" in capsys.readouterr().err
