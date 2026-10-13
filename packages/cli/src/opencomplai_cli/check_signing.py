"""Signing helpers for ``opencomplai check`` (kept out of main.py)."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path

from opencomplai_core.models import (
    CorroborationReport,
    EvalReport,
    ScanStatusArtifact,
)


def _lf_digest(data: bytes) -> str:
    """``sha256:<hex>`` of ``data`` with CRLF folded to LF (same on Windows/Linux)."""
    return "sha256:" + hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def with_input_hashes(
    artifact: ScanStatusArtifact,
    *,
    manifest_bytes: bytes | None,
    scan_report: CorroborationReport | None,
    eval_report: EvalReport | None,
) -> ScanStatusArtifact:
    """Append the digests of the files a local ``check`` read or wrote.

    Order: manifest, scan report, eval report; an input that is None is
    skipped. The report digests are taken over the exact model dump that
    ``_write_sidecar_reports`` writes, so they equal the on-disk sidecar
    digests. Hashes only, never content. Call before signing.
    """
    added = [
        _lf_digest(data)
        for data in (
            manifest_bytes,
            scan_report.model_dump_json(indent=2).encode("utf-8")
            if scan_report is not None
            else None,
            eval_report.model_dump_json(indent=2).encode("utf-8")
            if eval_report is not None
            else None,
        )
        if data is not None
    ]
    merged = list(dict.fromkeys([*artifact.evidence_hashes, *added]))
    if merged == artifact.evidence_hashes:
        return artifact
    return artifact.model_copy(update={"evidence_hashes": merged})


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
    repo_root: Path | None = None,
    tree: tuple[str, bool] | None = None,
) -> ScanStatusArtifact:
    """Fill the fields ``publish.prepare_scan_status_artifact`` would add at push,
    plus the four provenance stamps and the two tree stamps (``tree_sha256``,
    ``tree_dirty``), only when unset.

    Stamping before signing makes ``prepared == original`` at push time, so the
    signature survives. ``manifest_sha256`` stays None without ``manifest_bytes``;
    CRLF is hashed as LF so one manifest hashes the same on Windows and Linux.
    The tree stamps need ``repo_root`` to be a git work tree and stay None
    otherwise. A caller that sampled ``tree_provenance`` earlier passes it as
    ``tree`` so files the run itself generated are not counted.
    """
    from opencomplai_core.json_schemas import SCHEMA_VERSION
    from opencomplai_core.rules import RULE_SET_VERSION

    from opencomplai_cli.provenance import tree_provenance
    from opencomplai_cli.publish import _cli_version

    update: dict[str, object] = {}
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
    if repo_root is not None and not artifact.tree_sha256:
        stamped = tree if tree is not None else tree_provenance(repo_root)
        if stamped is not None:
            update["tree_sha256"], update["tree_dirty"] = stamped
    return artifact.model_copy(update=update) if update else artifact
