"""Gate semantics for a confirmed classification proposal.

`check --scan` calls this after the code scan. A proposal that a person
confirmed with a signed ``classification_proposal_confirmation`` record (see
``accept --proposal``) and that names an Annex III area the declared purpose
does not cover becomes one ``confirmed_proposal:<area>`` discrepancy row and
counts as at least MAJOR for ``--fail-on``. An absent, unconfirmed, edited or
stale proposal changes nothing, and the declared purpose stays the source of
the classification. A proposal's recorded code digest is current when it equals
the scan's manifest-aware digest or its legacy (0.12.0) digest.

The returned report copy is meant only as the argument of the fail-on gate:
the real ``CorroborationReport``, the ``scan-report.json`` sidecar and the gap
rows are never touched, so the report hash still covers the report. Pure
module: no clock, no network, no HOME; reads the repo root only.

Provenance of the MAJOR choice: source = product design, no external citation;
confidence = medium; needs_founder_review = true (severity choice).
"""

from __future__ import annotations

import os
from pathlib import Path

from opencomplai_core.acceptance import (
    PROPOSAL_CONFIRMATION,
    record_path,
    trusted_key_ids_from_env,
)
from opencomplai_core.classification_proposal import (
    PROPOSAL_FILENAME,
    confirmation_status,
    load_proposal,
    proposal_tree_sha256,
)
from opencomplai_core.models import (
    CorroborationReport,
    DiscrepancySeverity,
    ScanSummary,
    SignalCategory,
    SystemManifest,
)
from opencomplai_core.scanner.mapping import signal_category_to_taxonomy

ROW_PREFIX = "confirmed_proposal:"
_AT_LEAST_MAJOR = (DiscrepancySeverity.MAJOR, DiscrepancySeverity.CRITICAL)


def _evaluate(
    manifest: SystemManifest,
    repo_root: Path,
    current_tree_sha256: str | None,
    legacy_tree_sha256: str | None = None,
) -> tuple[str, dict | None]:
    """(status, proposal document when confirmed). Never raises."""
    try:
        root = repo_root.resolve()
        proposal_path = root / PROPOSAL_FILENAME
        if not proposal_path.is_file():
            return "absent", None
        status = confirmation_status(
            proposal_path,
            record_path(root, manifest.system_id, PROPOSAL_CONFIRMATION),
            manifest,
            trusted_key_ids=trusted_key_ids_from_env(os.environ),
        )
        if status.state == "stale":
            return "stale", None
        if status.state != "valid":
            return "unconfirmed", None
        doc = load_proposal(proposal_path)
        recorded = proposal_tree_sha256(doc)
        # A proposal from an older release has no digest: not comparable, so
        # it stays confirmed and behaves as before.
        # A proposal recorded by 0.12.0 holds the legacy digest, so either
        # value is current.
        current = {current_tree_sha256 or None, legacy_tree_sha256 or None}
        if recorded is not None and recorded not in current:
            return "stale", None
        return "confirmed", doc
    except Exception:
        return "unconfirmed", None


def proposal_status(
    manifest: SystemManifest,
    repo_root: Path,
    current_tree_sha256: str | None,
    legacy_tree_sha256: str | None = None,
) -> str:
    """One of absent, unconfirmed, stale, confirmed. Pure read; never raises."""
    return _evaluate(manifest, repo_root, current_tree_sha256, legacy_tree_sha256)[0]


def proposal_lacks_tree_digest(repo_root: Path) -> bool:
    """True when the proposal file on disk carries no code digest to compare."""
    try:
        doc = load_proposal(repo_root.resolve() / PROPOSAL_FILENAME)
    except ValueError:
        return False
    return proposal_tree_sha256(doc) is None


def confirmed_proposal_area(
    manifest: SystemManifest,
    repo_root: Path,
    current_tree_sha256: str | None = None,
    legacy_tree_sha256: str | None = None,
) -> int | None:
    """Annex III area (1-8) of a valid, confirmed, current proposal; else None.

    Never raises. A proposal written for other code (digest differs) is stale
    and returns None.
    """
    state, doc = _evaluate(manifest, repo_root, current_tree_sha256, legacy_tree_sha256)
    if state != "confirmed" or doc is None:
        return None
    area = doc["proposal"].get("proposed_annex_iii_area")
    if isinstance(area, int) and not isinstance(area, bool) and 1 <= area <= 8:
        return area
    return None


def apply_confirmed_proposal(
    summary: ScanSummary,
    report: CorroborationReport,
    area: int | None,
    baseline_categories: list[str] | None,
) -> tuple[ScanSummary, CorroborationReport]:
    """Add the confirmed-disagreement row; inputs are returned as is when none."""
    if area is None:
        return summary, report
    keys = signal_category_to_taxonomy(
        SignalCategory.SCORING_PROFILING, "", annex_iii_area=area
    )
    covered = set(report.declared_categories) | set(baseline_categories or [])
    rows = sorted({ROW_PREFIX + k for k in keys if k not in covered})
    if not rows:
        return summary, report
    discrepancies = list(dict.fromkeys([*summary.discrepancies, *rows]))
    severity = (
        summary.severity
        if summary.severity in _AT_LEAST_MAJOR
        else DiscrepancySeverity.MAJOR
    )
    update = {"discrepancies": discrepancies, "severity": severity}
    return summary.model_copy(update=update), report.model_copy(update=update)
