"""The native ISO/IEC 27090 pack: AI security guidance, attestation-led, flagged data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.frameworks import (
    FRAMEWORKS,
    FrameworkPack,
    evaluate_targets,
    gate_failures,
    load_requirements_map,
)
from opencomplai_core.models import (
    Attestation,
    ConfidenceLabel,
    EvalReport,
    EvaluatorCategory,
    EvaluatorOutcome,
    EvaluatorResult,
    FrameworkInputs,
    FrameworkScope,
    GapStatus,
    SystemManifest,
)

ISO = "ISO_IEC_27090"
_PACK = FRAMEWORKS[ISO]

IDS = [
    f"{ISO}:{c}"
    for c in (
        "5.1 5.2 5.3 5.4 5.5 5.6 5.7 6.2 6.3 6.4 6.5 6.6 6.7 6.8 6.9 6.10 6.11 "
        "7.2 7.3 7.4 7.5 7.6 7.7 7.8 7.9 B.2 B.3 B.4 B.5 B.6 B.7"
    ).split()
]

EVALUATOR_BACKED = {
    f"{ISO}:5.7": {"EVAL_ADVERSARIAL_V1"},
    f"{ISO}:6.8": {"EVAL_DATA_LEAKAGE_V1"},
    f"{ISO}:6.9": {"EVAL_ADVERSARIAL_V1", "EVAL_SAFETY_LEXICAL_V1"},
    f"{ISO}:6.10": {"EVAL_SAFETY_LEXICAL_V1"},
}

# Rows that also look for a file or code construct. That evidence only adds to the
# attestation (role "supporting"); it never decides a row by itself.
SUPPORTING = {
    f"{ISO}:5.5": {"ai_supply_chain_pins"},
    f"{ISO}:5.6": {"ai_threat_model"},
    f"{ISO}:5.7": {"ai_red_team_report"},
    f"{ISO}:6.5": {"rate_limiting_config"},
    f"{ISO}:7.5": {"event_log_evidence"},
    f"{ISO}:7.8": {"rate_limiting_config"},
    f"{ISO}:B.2": {"rate_limiting_config"},
    f"{ISO}:B.3": {"ai_supply_chain_pins"},
}

THREAT_MODEL = (
    "# Threat model\n\nAn attacker can use prompt injection in retrieved documents "
    "to make the assistant call tools it should not call.\n"
)


def _rows() -> dict[str, dict]:
    return load_requirements_map(_PACK.requirements)


def _manifest(**overrides: object) -> SystemManifest:
    return SystemManifest(
        system_id="sys", intended_purpose="support chatbot", **overrides
    )


def _attest(*ids: str) -> dict[str, FrameworkInputs]:
    attestation = Attestation(
        statement="Covered by the AI security standard.",
        attested_by="ciso@example.com",
        attested_at="2026-11-02",
    )
    return {ISO: FrameworkInputs(attested=dict.fromkeys(ids, attestation))}


def _report(manifest: SystemManifest, **kwargs):
    return evaluate_targets(manifest, [ISO], commit_ref="HEAD", **kwargs)[ISO]


def _eval_report(
    outcome: EvaluatorOutcome,
    evaluator_id: str = "EVAL_DATA_LEAKAGE_V1",
    category: EvaluatorCategory = EvaluatorCategory.DATA_LEAKAGE,
) -> EvalReport:
    result = EvaluatorResult(
        evaluator_id=evaluator_id,
        category=category,
        outcome=outcome,
        score=1.0 if outcome is EvaluatorOutcome.PASS else 0.0,
        threshold=0.9,
        metric_name="leak_free_rate",
        sample_count=10,
        reference="test",
        evidence_hash="sha256:00",
    )
    return EvalReport(
        system_id="sys",
        commit_ref="HEAD",
        eval_set_id="SET",
        eval_set_version="1",
        threshold_policy_hash="sha256:00",
        results=[result],
        evaluators_run=1,
        evaluators_failed=int(outcome is EvaluatorOutcome.FAIL),
        evaluators_skipped=0,
        overall_outcome=outcome,
        generated_at="2026-11-02T00:00:00Z",
    )


def test_every_row_is_flagged_data_in_table_of_contents_order():
    rows = _rows()
    assert list(rows) == IDS
    for rid, row in rows.items():
        assert 0 < len(row["title"]) <= 80, rid
        assert row["note"].strip(), rid
        assert row["source"].strip(), rid
        assert row["confidence"] == "low", rid
        assert row["needs_founder_review"] is True, rid


def test_rows_are_attestation_led_with_evaluators_only_where_they_check_the_row():
    evaluators = {}
    supporting = {}
    for rid, row in _rows().items():
        sources = row["sources"]
        assert {s["kind"] for s in sources} <= {"attestation", "evaluator", "artifact"}
        assert sources[0] == {"kind": "attestation", "ref": rid}, rid
        refs = {s["ref"] for s in sources if s["kind"] == "evaluator"}
        if refs:
            evaluators[rid] = refs
        # A probe is supporting evidence, never a row's own verdict.
        probes = [s for s in sources if s["kind"] == "artifact"]
        assert all(s["role"] == "supporting" for s in probes), rid
        if probes:
            supporting[rid] = {s["ref"] for s in probes}
    assert evaluators == EVALUATOR_BACKED
    assert supporting == SUPPORTING


def test_without_evidence_everything_is_unverified():
    report = _report(_manifest())
    assert report.derived_from is None
    assert report.disclaimer_ref == "DISCLAIMER_V2"
    assert len(report.report.articles) == 31
    assert {r.status for r in report.report.articles} == {GapStatus.UNVERIFIED}


def test_links_the_standard_names_itself():
    # ISO/IEC 27090:2026 5.1 points threat considerations to ISO/IEC 42001 A.6.2.3 and
    # A.6.2.6, and 5.1/5.3 name ISO/IEC 27002 8.15, 8.16 and 8.27.
    rows = _rows()
    for clause in "5.1 5.5 6.2 6.3 6.4 6.5 6.6 6.7 6.8 6.9 6.10".split():
        links = rows[f"{ISO}:{clause}"]["iso_42001"]
        assert {"ISO_IEC_42001:A.6.2.3", "ISO_IEC_42001:A.6.2.6"} <= set(links), clause
    assert {"A.8.15", "A.8.16", "A.8.27"} <= set(rows[f"{ISO}:5.1"]["iso_27001"])
    assert "A.8.27" in rows[f"{ISO}:5.3"]["iso_27001"]
    assert "A.8.15" in rows[f"{ISO}:7.5"]["iso_27001"]


def test_attestation_makes_an_attestation_only_row_met():
    rid = f"{ISO}:5.5"
    row = {
        r.article: r
        for r in _report(_manifest(framework_inputs=_attest(rid))).report.articles
    }[rid]
    assert row.status == GapStatus.MET
    assert row.confidence_label == ConfidenceLabel.ATTESTED
    with pytest.raises(ValueError, match=r"6.99"):
        _report(_manifest(framework_inputs=_attest(f"{ISO}:6.99")))


def test_a_supplied_eval_can_overrule_the_attestation():
    rid = f"{ISO}:6.8"
    attested = _manifest(framework_inputs=_attest(rid))
    # No eval supplied: the evaluator source is silent and the attestation stands.
    row = {r.article: r for r in _report(attested).report.articles}[rid]
    assert row.status == GapStatus.MET

    for outcome, expected in (
        (EvaluatorOutcome.PASS, GapStatus.MET),
        (EvaluatorOutcome.FAIL, GapStatus.MISSING),
    ):
        report = _report(attested, eval_report=_eval_report(outcome))
        assert {r.article: r for r in report.report.articles}[rid].status == expected


def test_exclusion_moves_row_to_excluded():
    rid = f"{ISO}:7.9"
    inputs = {
        ISO: FrameworkInputs(
            excluded={rid: "Model size is set by the hosted provider."}
        )
    }
    report = _report(_manifest(framework_inputs=inputs))
    assert rid not in {r.article for r in report.report.articles}
    assert report.excluded == {rid: "Model size is set by the hosted provider."}


# --- scoping: framework_inputs.ISO_IEC_27090.scope ---------------------------

# Rows each answer of false takes out on its own; 6.2 needs two answers.
SCOPED_OUT = {
    "trains_models": ["6.4", "6.6", "7.6", "7.9", "B.6"],
    "uses_retrieval": [],
    "public_api": ["6.5", "7.8", "B.2"],
}
NEVER_SCOPED = ["5.1", "5.5", "B.3", "6.9", "6.11", "B.7"]


def _scoped(
    excluded: dict[str, str] | None = None,
    attested: tuple[str, ...] = (),
    **answers: bool,
) -> SystemManifest:
    inputs = FrameworkInputs(
        scope=FrameworkScope(**answers),
        excluded=excluded or {},
        attested=_attest(*attested)[ISO].attested,
    )
    return _manifest(framework_inputs={ISO: inputs})


def _ids(*clauses: str) -> set[str]:
    return {f"{ISO}:{c}" for c in clauses}


def test_scope_out_follows_the_documented_table():
    scope_out = {
        rid: row["scope_out"] for rid, row in _rows().items() if "scope_out" in row
    }
    assert set(scope_out) == _ids(
        "6.2", *{c for rows in SCOPED_OUT.values() for c in rows}
    )
    assert scope_out[f"{ISO}:6.2"] == [["trains_models", "uses_retrieval"]]
    assert not set(scope_out) & _ids(*NEVER_SCOPED)


@pytest.mark.parametrize("answer", SCOPED_OUT)
def test_an_answer_of_no_excludes_exactly_its_rows(answer: str):
    report = _report(_scoped(**{answer: False}))
    assert set(report.excluded) == _ids(*SCOPED_OUT[answer])
    rows = {r.article for r in report.report.articles}
    assert not rows & set(report.excluded)
    assert len(rows) + len(report.excluded) == 31
    for reason in report.excluded.values():
        assert reason.startswith("Not applicable: the manifest's scope says")
        assert f"framework_inputs.{ISO}.scope.{answer} = false" in reason


def test_the_generated_reason_names_the_answer():
    report = _report(_scoped(public_api=False))
    assert report.excluded[f"{ISO}:6.5"] == (
        "Not applicable: the manifest's scope says the system is not reachable "
        "through a public API "
        "(framework_inputs.ISO_IEC_27090.scope.public_api = false)."
    )


@pytest.mark.parametrize("answer", SCOPED_OUT)
def test_an_answer_of_yes_or_none_excludes_nothing(answer: str):
    assert _report(_scoped(**{answer: True})).excluded == {}
    assert _report(_scoped()).excluded == {}


def test_data_poisoning_needs_no_training_and_no_retrieval():
    row = f"{ISO}:6.2"
    for answers in (
        {"trains_models": False},
        {"uses_retrieval": False},
        {"trains_models": False, "uses_retrieval": True},
        {"trains_models": True, "uses_retrieval": False},
    ):
        assert row not in _report(_scoped(**answers)).excluded
    both = _report(_scoped(trains_models=False, uses_retrieval=False))
    assert both.excluded[row] == (
        "Not applicable: the manifest's scope says the system does not train or "
        "fine-tune models and does not use retrieval over external content "
        "(framework_inputs.ISO_IEC_27090.scope.trains_models = false, "
        "framework_inputs.ISO_IEC_27090.scope.uses_retrieval = false)."
    )
    assert set(both.excluded) == _ids("6.2", *SCOPED_OUT["trains_models"])


def test_all_answers_of_no_never_touch_the_rows_a_hosted_model_still_has():
    report = _report(
        _scoped(
            trains_models=False,
            uses_retrieval=False,
            public_api=False,
        )
    )
    assert len(report.excluded) == 9
    assert not set(report.excluded) & _ids(*NEVER_SCOPED)
    assert len(report.report.articles) == 22


def test_an_explicit_exclusion_keeps_its_own_reason():
    rid = f"{ISO}:6.4"
    reason = "Model is licensed, not trained by us."
    report = _report(_scoped(excluded={rid: reason}, trains_models=False))
    assert report.excluded[rid] == reason
    assert set(report.excluded) == _ids(*SCOPED_OUT["trains_models"])


def test_an_attestation_keeps_a_row_the_scope_would_exclude():
    rid = f"{ISO}:7.9"
    report = _report(_scoped(attested=(rid,), trains_models=False))
    row = {r.article: r for r in report.report.articles}[rid]
    assert row.status == GapStatus.MET
    assert rid not in report.excluded
    assert set(report.excluded) == _ids(*SCOPED_OUT["trains_models"]) - {rid}


def test_unset_scope_changes_nothing():
    plain = _report(_manifest())
    empty = _report(_manifest(framework_inputs={ISO: FrameworkInputs()}))
    unanswered = _report(_scoped())
    assert plain.excluded == empty.excluded == unanswered.excluded == {}
    assert plain.report.articles == empty.report.articles == unanswered.report.articles


def test_a_gate_ignores_rows_the_scope_excluded(monkeypatch, tmp_path: Path):
    # 6.4 gets a failing evaluator source so that, unscoped, it would fail the gate.
    data = json.loads(_PACK.requirements.read_text(encoding="utf-8"))
    data[f"{ISO}:6.4"]["sources"].append(
        {"kind": "evaluator", "ref": "EVAL_DATA_LEAKAGE_V1"}
    )
    path = tmp_path / "iso_27090.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setitem(
        FRAMEWORKS, ISO, FrameworkPack(ISO, _PACK.label, requirements=path)
    )

    def failing(manifest: SystemManifest) -> list[str]:
        reports = evaluate_targets(
            manifest,
            [ISO],
            commit_ref="HEAD",
            eval_report=_eval_report(EvaluatorOutcome.FAIL),
        )
        return gate_failures(reports, [ISO], "missing")

    assert f"{ISO}:6.4" in failing(_manifest())
    assert f"{ISO}:6.4" in failing(_scoped(trains_models=True))
    assert f"{ISO}:6.4" not in failing(_scoped(trains_models=False))


# --- supporting probes: a file or code construct next to the attestation ---------


def _row(manifest: SystemManifest, rid: str, **kwargs):
    report = _report(manifest, **kwargs)
    return {r.article: r for r in report.report.articles}[rid]


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def test_supporting_evidence_without_an_attestation_stays_unverified(tmp_path: Path):
    rid = f"{ISO}:5.6"
    repo = _repo(tmp_path, {"docs/threat-model.md": THREAT_MODEL})
    row = _row(_manifest(), rid, repo_root=repo)
    assert row.status == GapStatus.UNVERIFIED
    assert row.source.value == "artifact"
    assert row.evidence_ref == "docs/threat-model.md"
    assert "Evidence found in docs/threat-model.md" in row.rationale
    assert "not attested" in row.rationale
    assert "framework_inputs.ISO_IEC_27090.attested" in row.rationale
    assert row.confidence_label == ConfidenceLabel.NOT_ASSESSED


def test_evidence_in_the_repository_cannot_fail_a_gate(tmp_path: Path):
    repo = _repo(tmp_path, {"docs/threat-model.md": THREAT_MODEL})
    reports = evaluate_targets(_manifest(), [ISO], commit_ref="HEAD", repo_root=repo)
    assert gate_failures(reports, [ISO], "partial") == []


def test_supporting_evidence_keeps_an_attested_row_met_and_names_the_file(
    tmp_path: Path,
):
    rid = f"{ISO}:5.6"
    repo = _repo(tmp_path, {"docs/threat-model.md": THREAT_MODEL})
    row = _row(_manifest(framework_inputs=_attest(rid)), rid, repo_root=repo)
    assert row.status == GapStatus.MET
    assert row.source.value == "attestation"
    assert row.confidence_label == ConfidenceLabel.ATTESTED
    # evidence_ref is what controls bind as evidence: it must not change.
    assert row.evidence_ref == "attestation:ciso@example.com@2026-11-02"
    assert row.rationale.startswith("Covered by the AI security standard.")
    assert "docs/threat-model.md (ai_threat_model)" in row.rationale


def test_a_supporting_probe_that_finds_nothing_changes_nothing(tmp_path: Path):
    rid = f"{ISO}:5.6"
    unattested = _manifest()
    attested = _manifest(framework_inputs=_attest(rid))
    for manifest, status in (
        (unattested, GapStatus.UNVERIFIED),
        (attested, GapStatus.MET),
    ):
        bare = _row(manifest, rid)  # no repo root at all
        assert bare.status == status
        assert _row(manifest, rid, repo_root=tmp_path) == bare


def test_a_file_without_the_content_markers_is_not_evidence(tmp_path: Path):
    repo = _repo(
        tmp_path,
        {
            "docs/threat-model.md": "# Threat model\n\nTo be written before the release.\n"
        },
    )
    row = _row(_manifest(), f"{ISO}:5.6", repo_root=repo)
    assert row.status == GapStatus.UNVERIFIED


def test_a_failing_evaluator_still_makes_the_row_missing(tmp_path: Path):
    rid = f"{ISO}:5.7"
    repo = _repo(
        tmp_path,
        {
            "docs/red-team-report.md": "Red team round one: prompt injection through "
            "uploaded documents. Results: three of ten attempts bypassed the filter.\n"
        },
    )
    fail = _eval_report(
        EvaluatorOutcome.FAIL, "EVAL_ADVERSARIAL_V1", EvaluatorCategory.ADVERSARIAL
    )
    for manifest in (_manifest(), _manifest(framework_inputs=_attest(rid))):
        row = _row(manifest, rid, repo_root=repo, eval_report=fail)
        assert (row.status, row.source.value) == (GapStatus.MISSING, "evaluator")
    # Without an eval the unattested row stays Unverified, pointing at the file.
    row = _row(_manifest(), rid, repo_root=repo)
    assert (row.status, row.evidence_ref) == (
        GapStatus.UNVERIFIED,
        "docs/red-team-report.md",
    )


def test_event_log_supports_logging_and_monitoring(tmp_path: Path):
    rid = f"{ISO}:7.5"
    repo = _repo(tmp_path, {".opencomplai/oversight-log.json": '{"seq": 1}\n'})
    row = _row(_manifest(), rid, repo_root=repo)
    assert (row.status, row.evidence_ref) == (
        GapStatus.UNVERIFIED,
        ".opencomplai/oversight-log.json",
    )
    attested = _manifest(framework_inputs=_attest(rid))
    assert _row(attested, rid, repo_root=repo).status == GapStatus.MET


def test_rate_limits_support_exactly_the_throttling_rows(tmp_path: Path):
    repo = _repo(tmp_path, {"app/main.py": "from slowapi import Limiter\n"})
    report = _report(_manifest(), repo_root=repo)
    assert {r.status for r in report.report.articles} == {GapStatus.UNVERIFIED}
    pointing = {r.article for r in report.report.articles if r.evidence_ref != "none"}
    assert pointing == {f"{ISO}:{c}" for c in ("6.5", "7.8", "B.2")}
    # The scope still takes the same rows out when the system has no public API.
    scoped = _report(_scoped(public_api=False), repo_root=repo)
    assert set(scoped.excluded) == pointing
    assert not pointing & {r.article for r in scoped.report.articles}
