"""Write the optional `check` report files (JUnit, SARIF, Markdown summary).

Best effort by design: a report that cannot be written warns and moves on, so
these flags can never change `check`'s exit code.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from opencomplai_core.ci_reports import (
    artifact_to_junit,
    artifact_to_sarif,
    artifact_to_summary_md,
)


def write_check_reports(
    artifact: dict,
    *,
    junit: Path | None,
    sarif: Path | None,
    summary_md: Path | None,
    location_uri: str,
    tool_version: str,
    warn: Callable[[str], None],
) -> None:
    outputs = (
        (junit, lambda: artifact_to_junit(artifact, "see compliance-artifact.json")),
        (
            sarif,
            lambda: (
                json.dumps(
                    artifact_to_sarif(artifact, location_uri, tool_version), indent=2
                )
                + "\n"
            ),
        ),
        (summary_md, lambda: artifact_to_summary_md(artifact) + "\n"),
    )
    for path, render in outputs:
        if path is None:
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(), encoding="utf-8", newline="\n")
        except OSError as exc:
            warn(f"could not write report {path}: {exc}")
