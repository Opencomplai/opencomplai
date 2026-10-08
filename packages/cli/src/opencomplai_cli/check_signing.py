"""Signing helpers for ``opencomplai check`` (kept out of main.py)."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path

from opencomplai_core.models import ScanStatusArtifact


def signing_key_available(key_path: Path) -> bool:
    """True when ``SIGNING_KEY_PRIVATE`` is set or the key file exists.

    The path is a parameter so ``main._SIGNING_KEY`` stays the patchable source.
    """
    return bool(os.environ.get("SIGNING_KEY_PRIVATE", "").strip()) or key_path.exists()


def stamp_artifact(
    artifact: ScanStatusArtifact,
    *,
    now: datetime,
    manifest_bytes: bytes | None = None,
) -> ScanStatusArtifact:
    """Fill the fields ``publish.prepare_scan_status_artifact`` would add at push,
    plus the four provenance stamps, only when unset.

    Stamping before signing makes ``prepared == original`` at push time, so the
    signature survives. ``manifest_sha256`` stays None without ``manifest_bytes``;
    CRLF is hashed as LF so one manifest hashes the same on Windows and Linux.
    """
    from opencomplai_core.json_schemas import SCHEMA_VERSION
    from opencomplai_core.rules import RULE_SET_VERSION

    from opencomplai_cli.publish import _cli_version

    update: dict[str, str] = {}
    if not artifact.timestamp:
        update["timestamp"] = now.isoformat().replace("+00:00", "Z")
    if not artifact.policy_bundle_version:
        update["policy_bundle_version"] = f"cli-{_cli_version()}"
    if not artifact.cli_version:
        update["cli_version"] = _cli_version()
    if not artifact.rule_set_version:
        update["rule_set_version"] = RULE_SET_VERSION
    if not artifact.schema_version:
        update["schema_version"] = SCHEMA_VERSION
    if not artifact.manifest_sha256 and manifest_bytes is not None:
        lf_bytes = manifest_bytes.replace(b"\r\n", b"\n")
        update["manifest_sha256"] = hashlib.sha256(lf_bytes).hexdigest()
    return artifact.model_copy(update=update) if update else artifact
