"""
GitLab CI connector (C1.5).

Wraps ``opencomplai check`` with GitLab CI platform conventions:

* Emits a GitLab-compatible JUnit XML artifact so the scan result appears
  in the test report panel (``--report-junit``).
* Creates a GitLab section for collapsible log output.
* Sets GitLab environment variables via ``dotenv`` artifact when the
  ``GL_ENV_FILE`` env var is set.
* Propagates exit code: ``result=control_fail`` → non-zero exit.
* Publishes the signed status artifact to the dashboard via the standard
  ingest path when configured.

Environment variables consumed
-------------------------------
``GITLAB_CI``                 — set to ``true`` by GitLab; connector detects.
``CI_COMMIT_SHA``             — used as ``commit_ref`` in annotations.
``CI_JOB_NAME``               — job name surfaced in summary.
``GL_ENV_FILE``               — path for dotenv artifact (optional).
``OPENCOMPLAI_DASHBOARD_URL`` — dashboard ingest base URL.
``OPENCOMPLAI_TENANT_ID``     — tenant ID.
``OPENCOMPLAI_AUTH_TOKEN``    — bearer token.

Exit codes
----------
0  — pass.
1  — control_fail or unexpected error.
2  — configuration error.

Usage in .gitlab-ci.yml
------------------------

```yaml
opencomplai-scan:
  image: python:3.11
  before_script:
    - pip install opencomplai
  script:
    - opencomplai-gitlab-connector
  artifacts:
    reports:
      junit: opencomplai-report.xml
    dotenv: opencomplai.env
  variables:
    OPENCOMPLAI_DASHBOARD_URL: $OPENCOMPLAI_DASHBOARD_URL
    OPENCOMPLAI_TENANT_ID: $OPENCOMPLAI_TENANT_ID
    OPENCOMPLAI_AUTH_TOKEN: $OPENCOMPLAI_AUTH_TOKEN
    GL_ENV_FILE: opencomplai.env
```
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from typing import Any

RUNNING_IN_GITLAB = os.environ.get("GITLAB_CI") == "true"


# ---------------------------------------------------------------------------
# GitLab log section helpers
# ---------------------------------------------------------------------------

_SECTION_START = "\x1b[0Ksection_start:{ts}:{name}\r\x1b[0K{title}"
_SECTION_END = "\x1b[0Ksection_end:{ts}:{name}\r\x1b[0K"


def _section_start(name: str, title: str) -> None:
    import time

    ts = int(time.time())
    print(_SECTION_START.format(ts=ts, name=name, title=title), flush=True)


def _section_end(name: str) -> None:
    import time

    ts = int(time.time())
    print(_SECTION_END.format(ts=ts, name=name), flush=True)


# ---------------------------------------------------------------------------
# JUnit XML generation
# ---------------------------------------------------------------------------


def _build_junit_xml(artifact: dict | None, stdout: str) -> str:
    suite = ET.Element("testsuite", name="opencomplai", tests="1")
    case = ET.SubElement(
        suite, "testcase", name="compliance-scan", classname="opencomplai"
    )

    if artifact:
        result = artifact.get("result", "unknown")
        if result == "control_fail":
            failed = artifact.get("failed_controls", [])
            failure = ET.SubElement(
                case,
                "failure",
                message=f"control_fail: {', '.join(str(f) for f in failed)}",
            )
            failure.text = stdout
        elif result == "trap_detected":
            warn = ET.SubElement(case, "system-out")
            warn.text = "trap_detected — review required"
    else:
        ET.SubElement(case, "error", message="No artifact result parsed")

    return ET.tostring(suite, encoding="unicode", xml_declaration=False)


# ---------------------------------------------------------------------------
# Core connector
# ---------------------------------------------------------------------------


def run_connector(
    check_args: list[str] | None = None,
    env: dict[str, str] | None = None,
    junit_path: str = "opencomplai-report.xml",
) -> int:
    """
    Run ``opencomplai check --sign`` and handle GitLab CI conventions.

    Returns 0 (pass) or 1 (fail).
    """
    _env = {**os.environ, **(env or {})}

    _section_start("opencomplai_scan", "Opencomplai compliance scan")

    cmd = ["opencomplai", "check", "--sign"] + (check_args or [])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=_env)
    except FileNotFoundError:
        print(
            "ERROR: opencomplai CLI not found. Install with: pip install opencomplai",
            file=sys.stderr,
        )
        _section_end("opencomplai_scan")
        return 2

    stdout = result.stdout
    if stdout:
        print(stdout, end="", flush=True)

    _section_end("opencomplai_scan")

    artifact_result = _parse_artifact_result(stdout)
    scan_result = artifact_result.get("result", "") if artifact_result else ""

    # JUnit XML artifact.
    xml_content = _build_junit_xml(artifact_result, stdout)
    try:
        with open(junit_path, "w") as fh:
            fh.write(xml_content)
    except OSError:
        pass

    # dotenv artifact for downstream jobs.
    gl_env_file = _env.get("GL_ENV_FILE", "")
    if gl_env_file and artifact_result:
        _write_dotenv(gl_env_file, artifact_result)

    # Dashboard publish.
    _publish_to_dashboard(artifact_result, _env)

    # Exit code propagation.
    if scan_result == "control_fail":
        print(
            f"FAIL: control_fail — {', '.join(str(c) for c in (artifact_result or {}).get('failed_controls', []))}"
        )
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


def _write_dotenv(path: str, artifact: dict) -> None:
    lines = [
        f"OPENCOMPLAI_RESULT={artifact.get('result', '')}",
        f"OPENCOMPLAI_SYSTEM_ID={artifact.get('system_id', '')}",
        f"OPENCOMPLAI_CONTENT_HASH={artifact.get('content_hash', '')}",
    ]
    try:
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


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
        print(f"WARNING: dashboard publish failed: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    sys.exit(run_connector())


__all__ = ["RUNNING_IN_GITLAB", "main", "run_connector"]
