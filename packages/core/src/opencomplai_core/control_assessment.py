"""Derive persistent control instances from a gaps run (CTRL-ASSESS).

Pure projection: turns the stateless per-run `ArticleGapStatus` rows of a
`GapReport` into persistent `ControlInstance` rows bound to evidence. This is
the behavioral heart of Gap A — a `GapReport` is recomputed fresh on every
`opencomplai gaps`/`check` run, but a `ControlInstance` is a durable record
that accumulates owner/TTL/waiver state across runs.

E-8 (obligation identity for gaps-derived controls): one control per article
per system, `obligation_id = article_ref = row.article`. No I/O, no logging —
callers own fetching `existing_controls` (e.g. from the evidence vault) and
persisting the returned list.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta

from opencomplai_core.control_catalog import ControlCatalogEntry
from opencomplai_core.control_identity import make_control_id
from opencomplai_core.models import (
    ArticleGapSource,
    ControlInstance,
    ControlsSummary,
    ControlState,
    ControlSummaryRow,
    GapReport,
    GapStatus,
    SystemManifest,
)


def _due_at(last_evidence_at: str | None, effective_ttl_days: int | None) -> str | None:
    """`last_evidence_at + effective_ttl_days` as ISO-8601, or None if either input is absent."""
    if last_evidence_at is None or effective_ttl_days is None:
        return None
    evidenced_at = datetime.fromisoformat(last_evidence_at)
    return (evidenced_at + timedelta(days=effective_ttl_days)).isoformat()


def derive_controls(
    gap_report: GapReport,
    manifest: SystemManifest,
    catalog: Mapping[str, ControlCatalogEntry],
    existing_controls: Iterable[ControlInstance] = (),
    *,
    tenant_id: str = "oss-default",
    now: str | None = None,
    excluded: Mapping[str, str] = {},
) -> list[ControlInstance]:
    """Derive one `ControlInstance` per `gap_report.articles` row (E-8).

    MET rows become `satisfied`, binding the row's `evidence_ref` into the
    control's `evidence_refs`, with `last_evidence_at` set to `now`. If the
    existing control already carried other evidence refs (e.g. attached
    manually via `opencomplai controls attach-evidence`), those are kept —
    the result is the union of the existing refs and `row.evidence_ref`,
    deduplicated, existing order preserved.

    PARTIAL/MISSING/UNVERIFIED rows normally become `evidence_missing` —
    evidence seen on a prior run is not deleted, `evidence_refs`/
    `last_evidence_at` are carried forward from the existing instance (if
    any), since only the *state* says evidence is missing now.

    E-10 exception: when the existing control is already `SATISFIED` with
    non-empty `evidence_refs` (i.e. it carries human-attached evidence), and
    the row's `source` is `ArticleGapSource.ARTIFACT` (a heuristic file
    probe) or the row's `status` is `UNVERIFIED`, the control is left
    `SATISFIED` instead — its `evidence_refs`, `last_evidence_at`, and
    `due_at` are carried forward verbatim (only `last_assessed_at` moves to
    `now`). A heuristic probe or an unverified obligation is not a hard
    signal that the previously-attached evidence stopped applying, so it
    must not clobber it; only evidence freshness (TTL expiry) or a manifest
    change is allowed to stale it out (see `control_freshness.py`). A
    PARTIAL/MISSING row whose `source` is RULE/OBLIGATION/SCAN/EVALUATOR is
    a hard signal and still downgrades to `evidence_missing` as before,
    regardless of any manually-attached evidence.

    An existing instance already in `ControlState.WAIVED` is returned
    unchanged: a human waiver is never overwritten by an automated
    assessment. Otherwise `owner`, `ttl_days`, and `waiver_rationale` are
    always copied verbatim from the existing instance with the same
    `control_id` (never set or cleared by this function).

    `catalog` is looked up by `row.article`; a missing entry does not fail —
    the derived control simply has no catalog TTL to inherit (`ttl_days`
    stays whatever the existing instance had, typically None).

    `excluded` maps requirement ids the manifest declares out of scope
    (`framework_inputs.<FW>.excluded`, already removed from the report's
    rows) to their justification. Each becomes a `WAIVED` control appended
    after the row-derived ones, with the justification as its
    `waiver_rationale`; owner, TTL and evidence carry over from the existing
    instance.
    """
    resolved_now = now if now is not None else datetime.now(UTC).isoformat()
    existing_by_id = {c.control_id: c for c in existing_controls}

    derived: list[ControlInstance] = []
    for row in gap_report.articles:
        obligation_id = row.article
        control_id = make_control_id(tenant_id, manifest.system_id, obligation_id)
        existing = existing_by_id.get(control_id)

        if existing is not None and existing.state == ControlState.WAIVED:
            derived.append(existing)
            continue

        owner = existing.owner if existing is not None else None
        ttl_days = existing.ttl_days if existing is not None else None
        waiver_rationale = existing.waiver_rationale if existing is not None else None

        catalog_entry = catalog.get(obligation_id)
        effective_ttl_days = (
            ttl_days
            if ttl_days is not None
            else (catalog_entry.default_ttl_days if catalog_entry is not None else None)
        )

        # E-10: a heuristic ARTIFACT probe or an UNVERIFIED obligation is not
        # a hard failure signal — it must not clobber evidence a human
        # already attached. Only a RULE/OBLIGATION/SCAN/EVALUATOR row (or an
        # existing control with no evidence to protect) still hard-downgrades.
        manual_evidence_survives = (
            row.status != GapStatus.MET
            and existing is not None
            and existing.state == ControlState.SATISFIED
            and bool(existing.evidence_refs)
            and (
                row.source == ArticleGapSource.ARTIFACT
                or row.status == GapStatus.UNVERIFIED
            )
        )

        if row.status == GapStatus.MET:
            state = ControlState.SATISFIED
            if existing is not None and existing.evidence_refs:
                evidence_refs = list(existing.evidence_refs)
                if row.evidence_ref not in evidence_refs:
                    evidence_refs.append(row.evidence_ref)
            else:
                evidence_refs = [row.evidence_ref]
            last_evidence_at = resolved_now
            due_at = _due_at(last_evidence_at, effective_ttl_days)
        elif manual_evidence_survives:
            assert existing is not None  # narrowed by manual_evidence_survives
            state = ControlState.SATISFIED
            evidence_refs = list(existing.evidence_refs)
            last_evidence_at = existing.last_evidence_at
            due_at = existing.due_at
        else:
            state = ControlState.EVIDENCE_MISSING
            evidence_refs = list(existing.evidence_refs) if existing is not None else []
            last_evidence_at = (
                existing.last_evidence_at if existing is not None else None
            )
            due_at = _due_at(last_evidence_at, effective_ttl_days)

        derived.append(
            ControlInstance(
                control_id=control_id,
                tenant_id=tenant_id,
                system_id=manifest.system_id,
                obligation_id=obligation_id,
                article_ref=obligation_id,
                owner=owner,
                state=state,
                evidence_refs=evidence_refs,
                ttl_days=ttl_days,
                last_assessed_at=resolved_now,
                last_evidence_at=last_evidence_at,
                due_at=due_at,
                waiver_rationale=waiver_rationale,
            )
        )

    for obligation_id, justification in excluded.items():
        control_id = make_control_id(tenant_id, manifest.system_id, obligation_id)
        existing = existing_by_id.get(control_id)
        waiver = {
            "state": ControlState.WAIVED,
            "last_assessed_at": resolved_now,
            "waiver_rationale": justification,
        }
        derived.append(
            existing.model_copy(update=waiver)
            if existing is not None
            else ControlInstance(
                control_id=control_id,
                tenant_id=tenant_id,
                system_id=manifest.system_id,
                obligation_id=obligation_id,
                article_ref=obligation_id,
                **waiver,
            )
        )

    return derived


def build_controls_block(controls: Iterable[ControlInstance]) -> ControlsSummary:
    """Project a derived control list into the artifact's optional `controls` block (CTRL-ARTIFACT).

    Pure, I/O-free: `summary` counts every `ControlState` value (zero-filled
    for states with no matching control), and `items` carries one
    `ControlSummaryRow` per control instance, in the same order as `controls`.
    """
    controls = list(controls)
    summary = {state.value: 0 for state in ControlState}
    for control in controls:
        summary[control.state.value] += 1

    items = [
        ControlSummaryRow(
            control_id=control.control_id,
            article_ref=control.article_ref,
            state=control.state,
            owner=control.owner,
            due_at=control.due_at,
        )
        for control in controls
    ]

    return ControlsSummary(summary=summary, items=items)
