"""Tests for CTRL-ASSESS: deriving control instances from a gaps run.

Builds small deterministic `GapReport` fixtures (one MET row, one MISSING
row) rather than driving the full rule engine — `gap_report.py`'s own tests
already cover article-map projection; this module is only responsible for
the GapReport -> ControlInstance projection in `control_assessment.py`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from opencomplai_core.control_assessment import build_controls_block, derive_controls
from opencomplai_core.control_catalog import ControlCatalogEntry, get_catalog
from opencomplai_core.control_identity import make_control_id
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    ControlInstance,
    ControlState,
    GapReport,
    GapStatus,
    SystemManifest,
)

TENANT_ID = "tenant-a"
NOW = "2026-08-17T00:00:00+00:00"

FIXTURE_PACK = FrameworkPack(
    "FIXTURE",
    "Fixture framework",
    requirements=Path(__file__).parent
    / "fixtures"
    / "framework_pack"
    / "requirements.json",
)


def _manifest(**overrides: object) -> SystemManifest:
    base: dict[str, object] = {
        "system_id": "sys-1",
        "intended_purpose": "credit scoring",
        "compliance_target": "EU_AI_ACT",
        "high_risk_presumption": True,
        "commit_ref": "abc123",
        "training_data_description": "internal loan applications 2018-2024",
        "model_architecture": "gradient boosted trees",
        "operator_role": "provider",
    }
    base.update(overrides)
    return SystemManifest(**base)


def _row(
    article: str,
    status: GapStatus,
    evidence_ref: str,
    *,
    source: ArticleGapSource = ArticleGapSource.RULE,
) -> ArticleGapStatus:
    return ArticleGapStatus(
        article=article,
        status=status,
        source=source,
        evidence_ref=evidence_ref,
        rationale="test fixture row",
        confidence=0.9 if status == GapStatus.MET else None,
        confidence_label=(
            ConfidenceLabel.MEASURED
            if status == GapStatus.MET
            else ConfidenceLabel.NOT_ASSESSED
        ),
    )


def _gap_report(rows: list[ArticleGapStatus]) -> GapReport:
    return GapReport(
        system_id="sys-1",
        commit_ref="abc123",
        generated_at=NOW,
        articles=rows,
    )


MET_ROW = _row("Art. 9", GapStatus.MET, "RULE_ART9_RISK_MGMT")
MISSING_ROW = _row("Art. 10", GapStatus.MISSING, "RULE_ART10_DATA_GOV")


def test_fresh_derive_creates_one_control_per_article_with_deterministic_ids():
    report = _gap_report([MET_ROW, MISSING_ROW])
    manifest = _manifest()

    derived = derive_controls(
        report, manifest, get_catalog(), tenant_id=TENANT_ID, now=NOW
    )

    assert len(derived) == 2
    by_article = {c.article_ref: c for c in derived}

    art9 = by_article["Art. 9"]
    assert art9.control_id == make_control_id(TENANT_ID, "sys-1", "Art. 9")
    assert art9.state == ControlState.SATISFIED
    assert art9.evidence_refs == ["RULE_ART9_RISK_MGMT"]
    assert art9.last_evidence_at == NOW
    assert art9.last_assessed_at == NOW

    art10 = by_article["Art. 10"]
    assert art10.control_id == make_control_id(TENANT_ID, "sys-1", "Art. 10")
    assert art10.state == ControlState.EVIDENCE_MISSING
    assert art10.evidence_refs == []
    assert art10.last_evidence_at is None
    assert art10.last_assessed_at == NOW


def test_deriving_twice_with_first_output_as_existing_is_idempotent():
    report = _gap_report([MET_ROW, MISSING_ROW])
    manifest = _manifest()

    first = derive_controls(
        report, manifest, get_catalog(), tenant_id=TENANT_ID, now=NOW
    )
    second = derive_controls(
        report, manifest, get_catalog(), first, tenant_id=TENANT_ID, now=NOW
    )

    assert len(second) == len(first) == 2
    assert {c.control_id for c in second} == {c.control_id for c in first}
    for a, b in zip(
        sorted(first, key=lambda c: c.control_id),
        sorted(second, key=lambda c: c.control_id),
        strict=True,
    ):
        assert a.owner == b.owner


def test_met_to_missing_transition_flips_state_but_preserves_owner_and_evidence():
    manifest = _manifest()
    first_report = _gap_report([MET_ROW])
    first = derive_controls(
        first_report, manifest, get_catalog(), tenant_id=TENANT_ID, now=NOW
    )
    with_owner = [
        c.model_copy(update={"owner": "compliance-team", "ttl_days": 45}) for c in first
    ]

    flipped_row = _row("Art. 9", GapStatus.MISSING, "RULE_ART9_RISK_MGMT")
    second_report = _gap_report([flipped_row])
    later = "2026-09-01T00:00:00+00:00"
    second = derive_controls(
        second_report,
        manifest,
        get_catalog(),
        with_owner,
        tenant_id=TENANT_ID,
        now=later,
    )

    assert len(second) == 1
    control = second[0]
    assert control.state == ControlState.EVIDENCE_MISSING
    assert control.owner == "compliance-team"
    assert control.ttl_days == 45
    assert control.waiver_rationale is None
    # Evidence seen on the earlier MET run is not deleted by the flip.
    assert control.evidence_refs == ["RULE_ART9_RISK_MGMT"]
    assert control.last_evidence_at == NOW
    assert control.last_assessed_at == later


def test_waived_existing_instance_is_never_overwritten():
    manifest = _manifest()
    control_id = make_control_id(TENANT_ID, "sys-1", "Art. 9")
    waived = ControlInstance(
        control_id=control_id,
        tenant_id=TENANT_ID,
        system_id="sys-1",
        obligation_id="Art. 9",
        article_ref="Art. 9",
        owner="compliance-team",
        state=ControlState.WAIVED,
        evidence_refs=[],
        ttl_days=None,
        last_assessed_at="2026-01-01T00:00:00+00:00",
        last_evidence_at=None,
        due_at=None,
        waiver_rationale="Accepted residual risk per ISO 31000 review.",
    )

    report = _gap_report([MISSING_ROW.model_copy(update={"article": "Art. 9"})])
    derived = derive_controls(
        report, manifest, get_catalog(), [waived], tenant_id=TENANT_ID, now=NOW
    )

    assert len(derived) == 1
    assert derived[0] == waived


def test_due_at_computed_from_catalog_ttl_when_evidence_present_else_none():
    manifest = _manifest()
    catalog = get_catalog()
    report = _gap_report([MET_ROW, MISSING_ROW])

    derived = derive_controls(report, manifest, catalog, tenant_id=TENANT_ID, now=NOW)
    by_article = {c.article_ref: c for c in derived}

    art9 = by_article["Art. 9"]
    ttl = catalog["Art. 9"].default_ttl_days
    assert ttl is not None
    from datetime import datetime, timedelta

    expected_due = (datetime.fromisoformat(NOW) + timedelta(days=ttl)).isoformat()
    assert art9.due_at == expected_due

    art10 = by_article["Art. 10"]
    assert art10.due_at is None


def test_missing_catalog_entry_does_not_fail_and_ttl_stays_none():
    manifest = _manifest()
    row = _row("Art. 999", GapStatus.MET, "SOME_EVIDENCE")
    report = _gap_report([row])
    catalog: dict[str, ControlCatalogEntry] = {}

    derived = derive_controls(report, manifest, catalog, tenant_id=TENANT_ID, now=NOW)

    assert len(derived) == 1
    control = derived[0]
    assert control.ttl_days is None
    assert control.due_at is None


def test_tenant_and_now_parameters_are_honoured():
    manifest = _manifest()
    report = _gap_report([MET_ROW])
    custom_now = "2030-01-01T00:00:00+00:00"

    derived = derive_controls(
        report, manifest, get_catalog(), tenant_id="tenant-z", now=custom_now
    )

    assert len(derived) == 1
    control = derived[0]
    assert control.tenant_id == "tenant-z"
    assert control.control_id == make_control_id("tenant-z", "sys-1", "Art. 9")
    assert control.last_assessed_at == custom_now
    assert control.last_evidence_at == custom_now


def test_now_defaults_to_current_utc_time_when_not_supplied():
    manifest = _manifest()
    report = _gap_report([MET_ROW])

    derived = derive_controls(report, manifest, get_catalog(), tenant_id=TENANT_ID)

    assert len(derived) == 1
    assert derived[0].last_assessed_at is not None


# ---------------------------------------------------------------------------
# E-10: manual evidence survives re-derivation
# ---------------------------------------------------------------------------


def _satisfied_with_manual_evidence(article: str = "Art. 9") -> ControlInstance:
    """An existing SATISFIED control carrying human-attached evidence, as
    `opencomplai controls attach-evidence` would leave it."""
    return ControlInstance(
        control_id=make_control_id(TENANT_ID, "sys-1", article),
        tenant_id=TENANT_ID,
        system_id="sys-1",
        obligation_id=article,
        article_ref=article,
        owner="compliance-team",
        state=ControlState.SATISFIED,
        evidence_refs=["sha256:manual-evidence-hash"],
        ttl_days=None,
        last_assessed_at="2026-01-01T00:00:00+00:00",
        last_evidence_at="2026-01-01T00:00:00+00:00",
        due_at="2026-04-01T00:00:00+00:00",
        waiver_rationale=None,
    )


def test_artifact_missing_keeps_manually_attached_evidence_satisfied():
    """A heuristic ARTIFACT-source probe going MISSING must not clobber
    evidence a human already attached — only freshness (TTL/manifest) may."""
    manifest = _manifest()
    existing = _satisfied_with_manual_evidence()

    artifact_missing_row = _row(
        "Art. 9",
        GapStatus.MISSING,
        "ARTIFACT_PROBE_ART9",
        source=ArticleGapSource.ARTIFACT,
    )
    report = _gap_report([artifact_missing_row])

    derived = derive_controls(
        report, manifest, get_catalog(), [existing], tenant_id=TENANT_ID, now=NOW
    )

    assert len(derived) == 1
    control = derived[0]
    assert control.state == ControlState.SATISFIED
    assert control.evidence_refs == existing.evidence_refs
    assert control.last_evidence_at == existing.last_evidence_at
    assert control.due_at == existing.due_at
    # last_assessed_at still moves forward even though nothing else changed.
    assert control.last_assessed_at == NOW


def test_unverified_status_keeps_manually_attached_evidence_satisfied():
    """An UNVERIFIED obligation (regardless of source) is not a hard failure
    signal either — same protection as an ARTIFACT probe."""
    manifest = _manifest()
    existing = _satisfied_with_manual_evidence()

    unverified_row = _row(
        "Art. 9",
        GapStatus.UNVERIFIED,
        "OBLIGATION_ART9_UNVERIFIED",
        source=ArticleGapSource.OBLIGATION,
    )
    report = _gap_report([unverified_row])

    derived = derive_controls(
        report, manifest, get_catalog(), [existing], tenant_id=TENANT_ID, now=NOW
    )

    assert len(derived) == 1
    control = derived[0]
    assert control.state == ControlState.SATISFIED
    assert control.evidence_refs == existing.evidence_refs
    assert control.due_at == existing.due_at


def test_rule_missing_still_downgrades_manually_attached_evidence():
    """A hard signal (RULE/OBLIGATION/SCAN/EVALUATOR source) with
    PARTIAL/MISSING still downgrades to evidence_missing even when the
    control was previously satisfied with manually-attached evidence — only
    ARTIFACT-source or UNVERIFIED rows get the E-10 protection."""
    manifest = _manifest()
    existing = _satisfied_with_manual_evidence()

    rule_missing_row = _row(
        "Art. 9",
        GapStatus.MISSING,
        "RULE_ART9_RISK_MGMT",
        source=ArticleGapSource.RULE,
    )
    report = _gap_report([rule_missing_row])

    derived = derive_controls(
        report, manifest, get_catalog(), [existing], tenant_id=TENANT_ID, now=NOW
    )

    assert len(derived) == 1
    control = derived[0]
    assert control.state == ControlState.EVIDENCE_MISSING
    # evidence is still carried forward, not deleted — only the state flips.
    assert control.evidence_refs == existing.evidence_refs
    assert control.last_evidence_at == existing.last_evidence_at


def test_met_row_unions_with_existing_manual_evidence_refs():
    """A MET row's evidence_ref is added to (not replacing) any evidence refs
    already on the existing control, deduplicated."""
    manifest = _manifest()
    existing = _satisfied_with_manual_evidence()
    assert existing.evidence_refs == ["sha256:manual-evidence-hash"]

    met_row = _row("Art. 9", GapStatus.MET, "RULE_ART9_RISK_MGMT")
    report = _gap_report([met_row])
    later = "2026-09-01T00:00:00+00:00"

    derived = derive_controls(
        report, manifest, get_catalog(), [existing], tenant_id=TENANT_ID, now=later
    )

    assert len(derived) == 1
    control = derived[0]
    assert control.state == ControlState.SATISFIED
    assert control.evidence_refs == [
        "sha256:manual-evidence-hash",
        "RULE_ART9_RISK_MGMT",
    ]
    assert control.last_evidence_at == later


def test_met_row_with_same_evidence_ref_does_not_duplicate():
    manifest = _manifest()
    existing = _satisfied_with_manual_evidence()
    existing = existing.model_copy(
        update={"evidence_refs": ["RULE_ART9_RISK_MGMT", "sha256:manual-evidence-hash"]}
    )

    met_row = _row("Art. 9", GapStatus.MET, "RULE_ART9_RISK_MGMT")
    report = _gap_report([met_row])

    derived = derive_controls(
        report, manifest, get_catalog(), [existing], tenant_id=TENANT_ID, now=NOW
    )

    assert len(derived) == 1
    assert derived[0].evidence_refs == [
        "RULE_ART9_RISK_MGMT",
        "sha256:manual-evidence-hash",
    ]


# ---------------------------------------------------------------------------
# CTRL-ARTIFACT: build_controls_block
# ---------------------------------------------------------------------------


def _control(
    article: str,
    state: ControlState,
    *,
    owner: str | None = None,
    due_at: str | None = None,
) -> ControlInstance:
    return ControlInstance(
        control_id=make_control_id(TENANT_ID, "sys-1", article),
        tenant_id=TENANT_ID,
        system_id="sys-1",
        obligation_id=article,
        article_ref=article,
        owner=owner,
        state=state,
        evidence_refs=[],
        ttl_days=None,
        last_assessed_at=NOW,
        last_evidence_at=None,
        due_at=due_at,
        waiver_rationale=None,
    )


def test_build_controls_block_counts_every_state_and_projects_rows():
    controls = [
        _control("Art. 9", ControlState.SATISFIED, owner="alice", due_at="2026-09-01"),
        _control("Art. 10", ControlState.EVIDENCE_MISSING),
        _control("Art. 11", ControlState.EVIDENCE_MISSING, owner="bob"),
        _control("Art. 12", ControlState.WAIVED),
    ]

    block = build_controls_block(controls)

    assert block.summary == {
        "satisfied": 1,
        "evidence_missing": 2,
        "evidence_stale": 0,
        "pending_review": 0,
        "waived": 1,
    }
    assert [row.control_id for row in block.items] == [c.control_id for c in controls]
    assert block.items[0].article_ref == "Art. 9"
    assert block.items[0].state == ControlState.SATISFIED
    assert block.items[0].owner == "alice"
    assert block.items[0].due_at == "2026-09-01"
    assert block.items[1].owner is None
    assert block.items[1].due_at is None


def test_build_controls_block_empty_list_zero_fills_every_state():
    block = build_controls_block([])

    assert block.summary == {
        "satisfied": 0,
        "evidence_missing": 0,
        "evidence_stale": 0,
        "pending_review": 0,
        "waived": 0,
    }
    assert block.items == []


# ---------------------------------------------------------------------------
# Other frameworks: prefixed ids, catalog TTLs and manifest exclusions.
# ---------------------------------------------------------------------------


def test_native_pack_row_uses_its_prefixed_id_and_pack_ttl(monkeypatch):
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
    row = _row(
        "FIXTURE:REQ-1",
        GapStatus.MET,
        "docs/risk_register.md",
        source=ArticleGapSource.ARTIFACT,
    )

    [control] = derive_controls(
        _gap_report([row]), _manifest(), get_catalog(), tenant_id=TENANT_ID, now=NOW
    )

    assert control.control_id == make_control_id(TENANT_ID, "sys-1", "FIXTURE:REQ-1")
    assert control.obligation_id == control.article_ref == "FIXTURE:REQ-1"
    assert control.state == ControlState.SATISFIED
    # FIXTURE:REQ-1 has default_ttl_days 180 in the fixture requirements map.
    expected_due = datetime.fromisoformat(NOW) + timedelta(days=180)
    assert control.due_at == expected_due.isoformat()


def test_excluded_requirements_become_waived_controls_after_the_rows():
    row = _row(
        "FIXTURE:REQ-1",
        GapStatus.MISSING,
        "risk_register",
        source=ArticleGapSource.ARTIFACT,
    )

    derived = derive_controls(
        _gap_report([row]),
        _manifest(),
        get_catalog(),
        tenant_id=TENANT_ID,
        now=NOW,
        excluded={"FIXTURE:REQ-3": "No deployers: internal tool only."},
    )

    assert [c.obligation_id for c in derived] == ["FIXTURE:REQ-1", "FIXTURE:REQ-3"]
    assert derived[1] == ControlInstance(
        control_id=make_control_id(TENANT_ID, "sys-1", "FIXTURE:REQ-3"),
        tenant_id=TENANT_ID,
        system_id="sys-1",
        obligation_id="FIXTURE:REQ-3",
        article_ref="FIXTURE:REQ-3",
        state=ControlState.WAIVED,
        last_assessed_at=NOW,
        waiver_rationale="No deployers: internal tool only.",
    )


def test_excluded_requirement_keeps_the_existing_owner_ttl_and_evidence():
    existing = ControlInstance(
        control_id=make_control_id(TENANT_ID, "sys-1", "FIXTURE:REQ-3"),
        tenant_id=TENANT_ID,
        system_id="sys-1",
        obligation_id="FIXTURE:REQ-3",
        article_ref="FIXTURE:REQ-3",
        owner="jane@example.com",
        state=ControlState.SATISFIED,
        evidence_refs=["sha256:aaaa"],
        ttl_days=30,
        last_assessed_at="2026-01-01T00:00:00+00:00",
        last_evidence_at="2026-01-01T00:00:00+00:00",
        due_at="2026-01-31T00:00:00+00:00",
    )

    derived = derive_controls(
        _gap_report([]),
        _manifest(),
        get_catalog(),
        [existing],
        tenant_id=TENANT_ID,
        now=NOW,
        excluded={"FIXTURE:REQ-3": "Out of scope."},
    )

    assert derived == [
        existing.model_copy(
            update={
                "state": ControlState.WAIVED,
                "last_assessed_at": NOW,
                "waiver_rationale": "Out of scope.",
            }
        )
    ]
