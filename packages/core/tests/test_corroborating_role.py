"""The "corroborating" source role: an attestation lifted only by found evidence."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from opencomplai_core.frameworks import gate_failures
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import (
    Attestation,
    ConfidenceLabel,
    EvalReport,
    EvaluatorCategory,
    EvaluatorOutcome,
    EvaluatorResult,
    FrameworkReport,
    GapStatus,
)

FW = "ISO_IEC_27090"
TODAY = date(2026, 11, 11)

REGISTER = (
    "# Risk register\n\nRisk assessment: identified risks and their mitigation "
    "and residual risk.\n"
)


def _attestation(valid_until: str | None = None) -> Attestation:
    return Attestation(
        statement="Reviewed by the security lead.",
        attested_by="ciso@example.com",
        attested_at="2026-11-02",
        valid_until=valid_until,
    )


def _row(*extra: dict) -> dict:
    return {
        "title": "t",
        "sources": [{"kind": "attestation", "ref": f"{FW}:1"}, *extra],
    }


def _artifact(ref: str, role: str | None = "corroborating") -> dict:
    source = {"kind": "artifact", "ref": ref}
    if role:
        source["role"] = role
    return source


def _eval_report(outcome: EvaluatorOutcome) -> EvalReport:
    result = EvaluatorResult(
        evaluator_id="EVAL_DATA_LEAKAGE_V1",
        category=EvaluatorCategory.DATA_LEAKAGE,
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


def _build(row: dict, repo: Path | None, *, attest=True, valid_until=None, **kw):
    rid = f"{FW}:1"
    report = build_gap_report(
        "sys",
        "HEAD",
        repo_root=repo,
        requirements={rid: row},
        attestations={rid: _attestation(valid_until)} if attest else {},
        today=TODAY,
        **kw,
    )
    return report.articles[0]


@pytest.fixture
def evidenced_repo(tmp_path: Path) -> Path:
    root = tmp_path / "evidenced"
    root.mkdir()
    (root / "risk_register.json").write_text(REGISTER, encoding="utf-8")
    return root


@pytest.fixture
def bare_file_repo(tmp_path: Path) -> Path:
    root = tmp_path / "bare"
    root.mkdir()
    (root / "risk_register.json").write_text("{}", encoding="utf-8")
    return root


def test_valid_attestation_with_evidence_is_met_and_corroborated(evidenced_repo):
    row = _build(_row(_artifact("risk_register")), evidenced_repo)
    assert row.status == GapStatus.MET
    assert row.source.value == "attestation"
    assert row.confidence_label == ConfidenceLabel.ATTESTED
    assert row.corroborated is True
    assert row.evidence_ref.startswith("attestation:")
    assert row.rationale.startswith("Reviewed by the security lead. Corroborated by ")
    assert row.rationale.endswith("(risk_register).")


def test_valid_attestation_with_bare_file_is_partial(bare_file_repo):
    row = _build(_row(_artifact("risk_register")), bare_file_repo)
    assert row.status == GapStatus.PARTIAL
    assert row.source.value == "attestation"
    assert row.corroborated is False
    assert row.rationale.startswith("Attested. Found ")


def test_valid_attestation_with_nothing_found_is_partial_not_missing(tmp_path):
    row = _build(_row(_artifact("risk_register")), tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.source.value == "attestation"
    assert row.confidence_label == ConfidenceLabel.ATTESTED
    assert row.corroborated is False
    assert row.rationale == "Attested, no supporting evidence found (risk_register)."


def test_valid_attestation_without_repo_root_is_the_plain_attested_row():
    row = _build(_row(_artifact("risk_register")), None)
    assert row.status == GapStatus.MET
    assert row.source.value == "attestation"
    assert row.corroborated is False
    assert row.rationale == "Reviewed by the security lead."


def test_no_attestation_the_probe_decides(tmp_path, evidenced_repo, bare_file_repo):
    row = _row(_artifact("risk_register"))
    missing = _build(row, tmp_path, attest=False)
    assert (missing.status, missing.source.value) == (GapStatus.MISSING, "artifact")
    assert missing.corroborated is None
    partial = _build(row, bare_file_repo, attest=False)
    assert (partial.status, partial.source.value) == (GapStatus.PARTIAL, "artifact")
    found = _build(row, evidenced_repo, attest=False)
    assert (found.status, found.source.value) == (GapStatus.PARTIAL, "artifact")
    assert found.corroborated is None


def test_no_attestation_and_no_repo_root_is_unverified():
    row = _build(_row(_artifact("risk_register")), None, attest=False)
    assert row.status == GapStatus.UNVERIFIED
    assert row.source.value == "attestation"
    assert row.corroborated is None


def test_expired_attestation_does_not_decide(tmp_path, evidenced_repo):
    row = _row(_artifact("risk_register"))
    missing = _build(row, tmp_path, valid_until="2026-11-01")
    assert (missing.status, missing.source.value) == (GapStatus.MISSING, "artifact")
    assert missing.corroborated is None
    found = _build(row, evidenced_repo, valid_until="2026-11-01")
    assert found.status == GapStatus.PARTIAL
    assert found.source.value == "artifact"
    nothing_ran = _build(row, None, valid_until="2026-11-01")
    assert nothing_ran.status == GapStatus.UNVERIFIED
    assert "expired" in nothing_ran.rationale


def test_worst_corroborating_probe_that_ran_is_the_one_reported(tmp_path):
    row = _row(_artifact("risk_register"), _artifact("ai_threat_model"))
    result = _build(row, tmp_path, attest=False)
    assert result.status == GapStatus.MISSING
    result = _build(row, tmp_path)
    assert result.rationale == (
        "Attested, no supporting evidence found (risk_register, ai_threat_model)."
    )


def test_any_evidenced_probe_corroborates(evidenced_repo):
    row = _row(_artifact("ai_threat_model"), _artifact("risk_register"))
    result = _build(row, evidenced_repo)
    assert result.status == GapStatus.MET
    assert result.corroborated is True
    assert result.rationale.endswith("(risk_register).")


def test_evaluator_corroboration():
    row = _row(
        {"kind": "evaluator", "ref": "EVAL_DATA_LEAKAGE_V1", "role": "corroborating"}
    )
    passed = _build(row, None, eval_report=_eval_report(EvaluatorOutcome.PASS))
    assert (passed.status, passed.source.value) == (GapStatus.MET, "attestation")
    assert passed.corroborated is True
    assert passed.rationale.endswith("(EVAL_DATA_LEAKAGE_V1).")
    failed = _build(row, None, eval_report=_eval_report(EvaluatorOutcome.FAIL))
    assert (failed.status, failed.source.value) == (GapStatus.PARTIAL, "attestation")
    assert failed.corroborated is False
    assert failed.rationale.startswith("Attested, no supporting evidence found")
    undecided = _build(
        row, None, eval_report=_eval_report(EvaluatorOutcome.FAIL), attest=False
    )
    assert (undecided.status, undecided.source.value) == (
        GapStatus.MISSING,
        "evaluator",
    )
    no_report = _build(row, None)
    assert no_report.status == GapStatus.MET
    assert no_report.corroborated is False


def test_a_deciding_source_still_wins_when_worse(evidenced_repo):
    row = _row(_artifact("risk_register"), _artifact("ai_threat_model", role=None))
    result = _build(row, evidenced_repo)
    assert (result.status, result.source.value) == (GapStatus.MISSING, "artifact")


def test_without_a_corroborating_source_rows_are_unchanged(evidenced_repo):
    row = _build(_row(_artifact("risk_register", role="supporting")), evidenced_repo)
    assert row.status == GapStatus.MET
    assert row.corroborated is None
    assert "corroborated" not in row.model_dump(mode="json")
    plain = _build(_row(), evidenced_repo)
    assert plain.status == GapStatus.MET
    assert "corroborated" not in plain.model_dump(mode="json")


def test_corroborated_is_serialised_only_when_set(evidenced_repo, tmp_path):
    row = _build(_row(_artifact("risk_register")), evidenced_repo)
    assert row.model_dump(mode="json")["corroborated"] is True
    nothing = _build(_row(_artifact("risk_register")), None)
    assert nothing.model_dump(mode="json")["corroborated"] is False


def test_gate_lists_the_unattested_missing_row(tmp_path):
    rows = {
        f"{FW}:1": _row(_artifact("risk_register")),
        f"{FW}:2": _row(_artifact("risk_register")),
    }
    rows[f"{FW}:2"]["sources"][0]["ref"] = f"{FW}:2"
    report = build_gap_report(
        "sys",
        "HEAD",
        repo_root=tmp_path,
        requirements=rows,
        attestations={f"{FW}:2": _attestation()},
        today=TODAY,
    )
    by_id = {r.article: r for r in report.articles}
    assert by_id[f"{FW}:1"].status == GapStatus.MISSING
    assert by_id[f"{FW}:2"].status == GapStatus.PARTIAL
    wrapped = {
        FW: FrameworkReport(
            framework=FW, label="x", data_version="v", disclaimer_ref="D", report=report
        )
    }
    assert gate_failures(wrapped, [FW], "missing") == [f"{FW}:1"]
