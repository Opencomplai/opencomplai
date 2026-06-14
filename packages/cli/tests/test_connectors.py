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

    def test_run_connector_control_fail_returns_1(self):
        from opencomplai_cli.connectors.github_actions import run_connector

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

    def test_run_connector_pass_returns_0(self):
        from opencomplai_cli.connectors.github_actions import run_connector

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

    def test_exit_code_propagation_trap_detected(self):
        from opencomplai_cli.connectors.github_actions import run_connector

        artifact = json.dumps(
            {"result": "trap_detected", "system_id": "s", "content_hash": "b" * 64}
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=0)
            code = run_connector(env={})

        # trap_detected is not a build failure.
        assert code == 0

    def test_set_output_written_to_file(self, tmp_path):
        from opencomplai_cli.connectors.github_actions import _set_output

        output_file = tmp_path / "outputs"
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            _set_output("result", "pass")

        content = output_file.read_text()
        assert "result=pass" in content


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

    def test_run_connector_control_fail_returns_1(self):
        from opencomplai_cli.connectors.gitlab_ci import run_connector

        artifact = json.dumps({"result": "control_fail", "failed_controls": ["c1"]})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=0)
            code = run_connector(env={}, junit_path=os.devnull)

        assert code == 1

    def test_run_connector_pass_returns_0(self):
        from opencomplai_cli.connectors.gitlab_ci import run_connector

        artifact = json.dumps({"result": "pass", "system_id": "s"})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=0)
            code = run_connector(env={}, junit_path=os.devnull)

        assert code == 0

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

    def test_junit_written_to_file(self, tmp_path):
        from opencomplai_cli.connectors.gitlab_ci import run_connector

        junit_path = str(tmp_path / "report.xml")
        artifact = json.dumps({"result": "pass", "system_id": "s"})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=artifact, stderr="", returncode=0)
            run_connector(env={}, junit_path=junit_path)

        content = open(junit_path).read()
        assert "testsuite" in content
