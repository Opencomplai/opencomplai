"""Gate semantics for a confirmed classification proposal.

`check --scan` calls this after the code scan. A proposal that a person
confirmed with a signed ``classification_proposal_confirmation`` record (see
``accept --proposal``) and that names an Annex III area the declared purpose
does not cover becomes one ``confirmed_proposal:<area>`` discrepancy row and
counts as at least MAJOR for ``--fail-on``. An absent, unconfirmed, edited or
stale proposal changes nothing, and the declared purpose stays the source of
the classification.

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


def confirmed_proposal_area(manifest: SystemManifest, repo_root: Path) -> int | None:
    """Annex III area (1-8) of a valid, confirmed proposal; else None. Never raises."""
    try:
        root = repo_root.resolve()
        proposal_path = root / PROPOSAL_FILENAME
        status = confirmation_status(
            proposal_path,
            record_path(root, manifest.system_id, PROPOSAL_CONFIRMATION),
            manifest,
            trusted_key_ids=trusted_key_ids_from_env(os.environ),
        )
        if status.state != "valid":
            return None
        area = load_proposal(proposal_path)["proposal"].get("proposed_annex_iii_area")
        if isinstance(area, int) and not isinstance(area, bool) and 1 <= area <= 8:
            return area
    except Exception:
        return None
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
