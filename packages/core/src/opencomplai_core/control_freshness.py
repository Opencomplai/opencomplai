"""Evidence freshness detection for the control instance registry (CTRL-FRESH).

Pure, no I/O: given a set of `ControlInstance` rows (and, optionally, the
`EvidenceObject`s they reference), compute which controls have gone stale
either because their evidence's TTL window expired (`detect_stale`) or
because the system's manifest changed since the evidence was recorded
(`detect_manifest_change`). Staleness is computed at read time by these two
functions — there is no cron, scheduler, or background worker. Callers
(risk-engine's `control_reassessment` module, today) run this on `gaps`/
`check`, persist the result via `apply_stale`, and enqueue a `ReviewItem` per
row via `services/risk-engine/src/opencomplai_risk_engine/review_queue.py`.

The module shape (Config dataclass, row dataclass, dedup key, read-time
detection, no dispatch) follows the policy-drift detector written earlier.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from opencomplai_core.models import ControlState

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from opencomplai_core.control_catalog import ControlCatalogEntry
    from opencomplai_core.models import ControlInstance, EvidenceObject


@dataclass(frozen=True)
class FreshnessConfig:
    """Fallback TTL applied after a control's own `ttl_days` and the control
    catalog's `default_ttl_days` have both been checked. `None` (the default)
    means a control with no instance- or catalog-level TTL never goes stale
    from age alone."""

    default_ttl_days: int | None = None


class StaleReason(StrEnum):
    TTL_EXPIRED = "ttl_expired"
    MANIFEST_CHANGED = "manifest_changed"


@dataclass(frozen=True)
class StaleControlRow:
    control_id: str
    system_id: str
    article_ref: str
    owner: str | None
    state: ControlState
    stale_reason: StaleReason
    expired_at: str | None
    dedup_key: str
    message: str


def stale_dedup_key(
    tenant_id: str, control_id: str, last_evidence_at: str | None
) -> str:
    """Deterministic dedup/idempotency key for a stale-control event.

    `sha256("CTRL_STALE|{tenant}|{control_id}|{last_evidence_at}")`. Stable
    across repeated runs against the same evidence so re-detecting the same
    stale control never enqueues a second `ReviewItem`.
    """
    raw = f"CTRL_STALE|{tenant_id}|{control_id}|{last_evidence_at}"
    return hashlib.sha256(raw.encode()).hexdigest()


def effective_ttl_days(
    control: ControlInstance,
    catalog: Mapping[str, ControlCatalogEntry],
    config: FreshnessConfig,
) -> int | None:
    """Resolve the fallback chain: instance override -> catalog default -> config default -> None."""
    if control.ttl_days is not None:
        return control.ttl_days
    catalog_entry = catalog.get(control.article_ref)
    if catalog_entry is not None and catalog_entry.default_ttl_days is not None:
        return catalog_entry.default_ttl_days
    return config.default_ttl_days


def control_expiry(
    control: ControlInstance,
    catalog: Mapping[str, ControlCatalogEntry],
    config: FreshnessConfig,
    evidence: Mapping[str, EvidenceObject] | None = None,
) -> str | None:
    """Compute the ISO-8601 timestamp at which `control`'s evidence expires.

    Precedence (EVID-PROV):
      1. The EARLIEST `valid_until` among the `EvidenceObject`s referenced by
         `control.evidence_refs` (looked up in `evidence`), if any is set.
      2. Else the EARLIEST `collected_at` among those evidence objects, plus
         the effective TTL, if any `collected_at` is set and a TTL applies.
      3. Else `control.due_at`, if set.
      4. Else `control.last_evidence_at` plus the effective TTL, if both are
         available.
      5. Else `None` — no TTL and no evidence timestamp to project from.
    """
    ttl_days = effective_ttl_days(control, catalog, config)
    referenced = (
        [evidence[ref] for ref in control.evidence_refs if ref in evidence]
        if evidence is not None
        else []
    )

    valid_untils = [e.valid_until for e in referenced if e.valid_until is not None]
    if valid_untils:
        return min(valid_untils)

    if ttl_days is not None:
        collected_ats = [
            e.collected_at for e in referenced if e.collected_at is not None
        ]
        if collected_ats:
            earliest = min(collected_ats)
            return (
                datetime.fromisoformat(earliest) + timedelta(days=ttl_days)
            ).isoformat()

    if control.due_at is not None:
        return control.due_at

    if control.last_evidence_at is not None and ttl_days is not None:
        return (
            datetime.fromisoformat(control.last_evidence_at) + timedelta(days=ttl_days)
        ).isoformat()

    return None


def detect_stale(
    controls: Iterable[ControlInstance],
    catalog: Mapping[str, ControlCatalogEntry],
    now: str | None = None,
    *,
    config: FreshnessConfig | None = None,
    evidence: Mapping[str, EvidenceObject] | None = None,
) -> list[StaleControlRow]:
    """TTL-expiry staleness (D4). Only `SATISFIED` controls can go stale from
    age — `WAIVED`, `EVIDENCE_MISSING`, `PENDING_REVIEW`, and already-
    `EVIDENCE_STALE` controls are skipped, since only a satisfied control has
    evidence whose freshness is meaningful to re-check. Deterministic input
    order; `now` is an ISO-8601 string, defaulting to the current UTC time.
    """
    cfg = config or FreshnessConfig()
    resolved_now = now if now is not None else datetime.now(UTC).isoformat()

    rows: list[StaleControlRow] = []
    for control in controls:
        if control.state != ControlState.SATISFIED:
            continue
        expiry = control_expiry(control, catalog, cfg, evidence)
        if expiry is None:
            continue
        if expiry >= resolved_now:
            continue
        rows.append(
            StaleControlRow(
                control_id=control.control_id,
                system_id=control.system_id,
                article_ref=control.article_ref,
                owner=control.owner,
                state=control.state,
                stale_reason=StaleReason.TTL_EXPIRED,
                expired_at=expiry,
                dedup_key=stale_dedup_key(
                    control.tenant_id, control.control_id, control.last_evidence_at
                ),
                message=f"Evidence for {control.article_ref} expired at {expiry}",
            )
        )
    return rows


def detect_manifest_change(
    controls: Iterable[ControlInstance],
    stored_fingerprint: str | None,
    current_fingerprint: str,
    *,
    now: str | None = None,
) -> list[StaleControlRow]:
    """Manifest-change staleness (D5).

    If there is no stored fingerprint yet (first sighting of this system) or
    the stored and current fingerprints are equal, nothing has changed and
    this returns `[]`.

    Otherwise, the manifest's compliance-relevant shape changed since the
    last run. A `SATISFIED` control is flagged only if its evidence predates
    *this* assessment run — i.e. `last_evidence_at is None` or
    `last_evidence_at < last_assessed_at`. A control whose evidence was
    freshly observed by this run's `derive_controls` pass has
    `last_evidence_at == last_assessed_at` (both set to the same `now` by
    that function) and is left satisfied: the manifest changed, but this
    control's evidence was (re-)confirmed against the new manifest shape in
    the same run, so it isn't stale relative to it.
    """
    if stored_fingerprint is None or stored_fingerprint == current_fingerprint:
        return []

    resolved_now = now if now is not None else datetime.now(UTC).isoformat()

    rows: list[StaleControlRow] = []
    for control in controls:
        if control.state != ControlState.SATISFIED:
            continue
        if control.last_evidence_at is not None and (
            control.last_assessed_at is None
            or control.last_evidence_at >= control.last_assessed_at
        ):
            continue
        rows.append(
            StaleControlRow(
                control_id=control.control_id,
                system_id=control.system_id,
                article_ref=control.article_ref,
                owner=control.owner,
                state=control.state,
                stale_reason=StaleReason.MANIFEST_CHANGED,
                expired_at=resolved_now,
                dedup_key=stale_dedup_key(
                    control.tenant_id, control.control_id, control.last_evidence_at
                ),
                message=(
                    f"Manifest changed since evidence for {control.article_ref} "
                    "was recorded"
                ),
            )
        )
    return rows


def apply_stale(
    controls: Iterable[ControlInstance], rows: Iterable[StaleControlRow]
) -> list[ControlInstance]:
    """Return copies of `controls` with `state=EVIDENCE_STALE` for every
    control named in `rows`; controls not named in `rows` are returned
    unchanged. Pure helper — the caller persists the result."""
    stale_ids = {row.control_id for row in rows}
    return [
        c.model_copy(update={"state": ControlState.EVIDENCE_STALE})
        if c.control_id in stale_ids
        else c
        for c in controls
    ]
