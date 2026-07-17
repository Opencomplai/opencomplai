"""CLI JSON envelope helpers — additive wrappers for scan/gaps/report output.

The signed CI contract remains `ScanStatusArtifact` from `opencomplai check`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from opencomplai_core import __version__
from opencomplai_core.models import DISCLAIMER_V1, ScanOutputEnvelope


def wrap_scan_output(
    payload: dict[str, Any],
    *,
    scan_errors: list[str] | None = None,
    tool_version: str | None = None,
) -> ScanOutputEnvelope:
    """Wrap a CLI payload in a versioned envelope (not a signed artifact)."""
    return ScanOutputEnvelope(
        tool_version=tool_version or __version__,
        disclaimer=DISCLAIMER_V1,
        generated_at=datetime.now(UTC).isoformat(),
        scan_errors=list(scan_errors or []),
        payload=payload,
    )
