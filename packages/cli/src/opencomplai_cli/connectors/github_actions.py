"""
GitHub Actions CI connector (C1.5).

Wraps the ``opencomplai check`` command with GitHub Actions platform
conventions:

* Sets a step output ``result`` to the artifact result value so downstream
  steps can consume it.
* Annotates the run summary via ``::notice::`` / ``::warning::`` / ``::error::``
  workflow commands.
* Propagates exit code: ``result=control_fail`` → non-zero exit (fails the build).
* Publishes the signed status artifact to the dashboard via the standard ingest
  path when ``OPENCOMPLAI_DASHBOARD_URL`` and a bootstrap token are configured.

Environment variables consumed
-------------------------------
``GITHUB_ACTIONS``           — set to ``true`` by GitHub; connector activates.
``GITHUB_OUTPUT``            — path to the step-output file.
``GITHUB_STEP_SUMMARY``      — path to the job summary markdown file.
``OPENCOMPLAI_DASHBOARD_URL`` — dashboard ingest base URL.
``OPENCOMPLAI_TENANT_ID``    — tenant ID for the current org.
``OPENCOMPLAI_AUTH_TOKEN``   — bearer token for dashboard ingest.

Exit codes
----------
0  — scan passed (result in {pass, trap_detected}).
1  — scan failed (result=control_fail) or unexpected error.
2  — configuration error (missing required env var, bad token, etc.).

Usage in a workflow step
------------------------

```yaml
- name: Opencomplai compliance scan
  uses: actions/setup-python@v5
  with: { python-version: "3.11" }
- run: pip install opencomplai
- run: opencomplai-gha-connector
  env:
    OPENCOMPLAI_DASHBOARD_URL: ${{ secrets.OPENCOMPLAI_DASHBOARD_URL }}
    OPENCOMPLAI_TENANT_ID: ${{ secrets.OPENCOMPLAI_TENANT_ID }}
    OPENCOMPLAI_AUTH_TOKEN: ${{ secrets.OPENCOMPLAI_AUTH_TOKEN }}
```
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Platform detection helpers
# ---------------------------------------------------------------------------

RUNNING_IN_GHA = os.environ.get("GITHUB_ACTIONS") == "true"


def _gha_cmd(cmd: str, value: str) -> None:
    """Write a GitHub Actions workflow command to stdout."""
    print(f"::{cmd}::{value}", flush=True)


def _set_output(name: str, value: str) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        with open(output_file, "a") as fh:
            fh.write(f"{name}={value}\n")
    else:
        _gha_cmd("set-output", f"name={name}::{value}")


def _append_summary(markdown: str) -> None:
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_file:
        with open(summary_file, "a") as fh:
            fh.write(markdown + "\n")


def _annotate(level: str, message: str) -> None:
    """level: notice | warning | error"""
    _gha_cmd(level, message)


# ---------------------------------------------------------------------------
# Core connector
# ---------------------------------------------------------------------------


def run_connector(
    check_args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """
    Run ``opencomplai check --sign`` and handle GHA platform conventions.

    ``check_args`` is appended to the base command (for testing).
    ``env`` overrides environment variables (for testing).

    Returns the process exit code (0 = pass, 1 = fail).
    """
    _env = {**os.environ, **(env or {})}

    cmd = ["opencomplai", "check", "--sign"] + (check_args or [])
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=_env,
        )
    except FileNotFoundError:
        msg = "opencomplai CLI not found. Install with: pip install opencomplai"
        _annotate("error", msg)
        return 2

    stdout = result.stdout
    stderr = result.stderr

    # Parse the signed artifact result from stdout (JSON line on stdout).
    artifact_result = _parse_artifact_result(stdout)

    # Set step output.
    if artifact_result:
        _set_output("result", artifact_result.get("result", "unknown"))
        _set_output("content_hash", artifact_result.get("content_hash", ""))

    # Annotate.
    scan_result = artifact_result.get("result", "") if artifact_result else ""
    if scan_result == "control_fail":
        _annotate(
            "error",
            f"Opencomplai: control_fail — {_failed_controls_summary(artifact_result)}",
        )
    elif scan_result == "trap_detected":
        _annotate("warning", "Opencomplai: trap_detected — review required")
    elif scan_result:
        _annotate("notice", f"Opencomplai: {scan_result}")

    # Job summary.
    _append_summary(_build_summary(artifact_result, stdout, stderr))

    # Publish to dashboard.
    _publish_to_dashboard(artifact_result, _env)

    # Exit code propagation: control_fail is a CI failure.
    if scan_result == "control_fail":
        return 1
    if result.returncode != 0 and not scan_result:
        return result.returncode
    return 0


def _parse_artifact_result(stdout: str) -> dict[str, Any] | None:
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
                if "result" in obj:
                    return obj
            except json.JSONDecodeError:
                pass
    return None


def _failed_controls_summary(artifact: dict | None) -> str:
    if not artifact:
        return "unknown"
    controls = artifact.get("failed_controls", [])
    if not controls:
        return "see output"
    return ", ".join(str(c) for c in controls[:5])


def _build_summary(artifact: dict | None, stdout: str, stderr: str) -> str:
    result = artifact.get("result", "unknown") if artifact else "unknown"
    system_id = artifact.get("system_id", "unknown") if artifact else "unknown"
    commit_ref = artifact.get("commit_ref", "") if artifact else ""
    lines = [
        "## Opencomplai Compliance Scan",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Result | `{result}` |",
        f"| System | `{system_id}` |",
        f"| Commit | `{commit_ref}` |",
    ]
    if artifact and artifact.get("failed_controls"):
        lines.append(f"| Failed controls | `{_failed_controls_summary(artifact)}` |")
    eval_summary = artifact.get("eval_summary") if artifact else None
    if isinstance(eval_summary, dict):
        lines.append(
            f"| Eval outcome | `{eval_summary.get('overall_outcome', 'n/a')}` |"
        )
    elif artifact and artifact.get("eval_overall_outcome"):
        lines.append(f"| Eval outcome | `{artifact['eval_overall_outcome']}` |")
    return "\n".join(lines)


def _publish_to_dashboard(artifact: dict | None, env: dict[str, str]) -> None:
    if not artifact:
        return
    base_url = env.get("OPENCOMPLAI_DASHBOARD_URL", "").rstrip("/")
    token = env.get("OPENCOMPLAI_AUTH_TOKEN", "")
    if not base_url or not token:
        return

    import urllib.error
    import urllib.request

    install_id = env.get("OPENCOMPLAI_INSTALL_ID", "unknown")
    payload = {
        "install_id": install_id,
        "system_id": artifact.get("system_id", "unknown"),
        "artifact": artifact,
        "signature": artifact.get("signature", ""),
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base_url}/v1/ingest/scan-status",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30):
            pass
    except Exception as exc:
        _annotate("warning", f"Opencomplai dashboard publish failed: {exc}")


# ---------------------------------------------------------------------------
# Entry point (pip-installed script)
# ---------------------------------------------------------------------------


def main() -> None:
    sys.exit(run_connector())


__all__ = ["RUNNING_IN_GHA", "main", "run_connector"]
