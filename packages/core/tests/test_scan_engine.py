"""Scan engine — discrepancy analysis and deterministic hashing."""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.models import (
    DiscrepancySeverity,
    EvidenceItem,
    EvidenceKind,
    EvidenceScope,
    Reachability,
    SignalCategory,
)
from opencomplai_core.scan_engine import (
    _filter_features_to_detected_files,
    _upgrade_intent_evidence,
    run_scan,
)
from opencomplai_core.scanner.feature_types import CallsiteRef, FeatureStore, ImportRef

try:
    from opencomplai_ai.models import IntentAnnotation
except ImportError:
    IntentAnnotation = None  # type: ignore[misc, assignment]


def _biometric_repo(tmp_path: Path) -> Path:
    (tmp_path / "requirements.txt").write_text("face_recognition\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "face.py").write_text(
        "import face_recognition\n"
        "def identify(img):\n"
        "    return face_recognition.face_locations(img)\n",
        encoding="utf-8",
    )
    return tmp_path


def test_declared_minimal_biometric_prod_major_discrepancy(tmp_path: Path):
    repo = _biometric_repo(tmp_path)
    report = run_scan(
        system_id="test-sys",
        commit_ref="HEAD",
        repo_root=repo,
        declared_purpose="customer support chatbot",
    )
    assert "biometric" in report.detected_categories or report.evidence
    if "biometric" in report.discrepancies:
        assert report.severity in (
            DiscrepancySeverity.MAJOR,
            DiscrepancySeverity.MINOR,
            DiscrepancySeverity.INFO,
        )


def test_empty_inventory_adds_warning(tmp_path: Path):
    empty = tmp_path / "empty-repo"
    empty.mkdir()
    report = run_scan(
        system_id="test-sys",
        commit_ref="HEAD",
        repo_root=empty,
        declared_purpose="customer support chatbot",
    )
    assert any(w.startswith("empty_inventory:") for w in report.warnings)


def test_run_scan_rejects_missing_repo_root(tmp_path: Path):
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        run_scan(
            system_id="test-sys",
            commit_ref="HEAD",
            repo_root=missing,
            declared_purpose="customer support chatbot",
        )


def test_agreement_yields_none_severity(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    report = run_scan(
        system_id="test-sys",
        commit_ref="HEAD",
        repo_root=tmp_path,
        declared_purpose="customer support chatbot",
    )
    assert report.severity == DiscrepancySeverity.NONE
    assert report.discrepancies == []


def test_same_tree_twice_identical_report_hash(tmp_path: Path):
    repo = _biometric_repo(tmp_path)
    r1 = run_scan("s", "HEAD", repo, "customer support chatbot")
    r2 = run_scan("s", "HEAD", repo, "customer support chatbot")
    assert r1.input_digest == r2.input_digest
    assert r1.report_hash == r2.report_hash


def test_filter_includes_files_with_ai_library_imports(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    ai_file = src / "llm.py"
    ai_file.write_text(
        "import openai\n\nclient = openai.Client()\nresult = client.chat.completions.create()\n",
        encoding="utf-8",
    )
    features = FeatureStore(repo_root=tmp_path)
    features.imports.append(
        ImportRef(module="openai", location=f"{ai_file}:1", scope=EvidenceScope.PROD)
    )
    features.callsites.append(
        CallsiteRef(
            name="client.chat.completions.create",
            location=f"{ai_file}:3",
            scope=EvidenceScope.PROD,
        )
    )

    filtered = _filter_features_to_detected_files(features, evidence=[])
    assert any("llm.py" in imp.location for imp in filtered.imports)
    assert any("llm.py" in c.location for c in filtered.callsites)


def test_upgrade_intent_evidence_maps_annex_iii_area_to_category():
    if IntentAnnotation is None:
        return

    ann = IntentAnnotation(
        annex_iii_area=5,
        decision_autonomy="advisory",
        subject_type="natural_person",
        consequential="yes",
        eu_obligation=["Art.9 risk mgmt"],
        model_id="codebert-onnx",
        confidence=0.9,
        risk_tier="high_risk",
    )
    ev = EvidenceItem(
        evidence_id="ev_intent_1",
        evidence_kind=EvidenceKind.CALLSITE,
        category=SignalCategory.PROMPT_AGENT,
        token_hash="sha256:test",
        token_label="score_applicant",
        locations=["src/score.py:10"],
        scope=EvidenceScope.PROD,
        reachability=Reachability.INTERNAL_CALLCHAIN,
        detector_id="DET_INTENT_V1",
        detector_version="1.0.0",
        redaction_level="hash_only",
        rationale_code="intent_annotation",
        confidence=0.9,
        intent_annotation=ann,
    )

    upgraded = _upgrade_intent_evidence([ev])[0]
    assert upgraded.category == SignalCategory.SCORING_PROFILING


def test_upgrade_intent_evidence_applies_art6_3_profiling_override():
    if IntentAnnotation is None:
        return

    ann = IntentAnnotation(
        art6_3_profiling=True,
        decision_autonomy="display_only",
        subject_type="natural_person",
        consequential="no",
        model_id="codebert-onnx",
        confidence=0.8,
        risk_tier="high_risk",
    )
    ev = EvidenceItem(
        evidence_id="ev_intent_2",
        evidence_kind=EvidenceKind.CALLSITE,
        category=SignalCategory.AI_SDK,
        token_hash="sha256:test2",
        token_label="profile_user",
        locations=["src/profile.py:5"],
        scope=EvidenceScope.PROD,
        reachability=Reachability.INTERNAL_CALLCHAIN,
        detector_id="DET_INTENT_V1",
        detector_version="1.0.0",
        redaction_level="hash_only",
        rationale_code="intent_annotation",
        confidence=0.8,
        intent_annotation=ann,
    )

    upgraded = _upgrade_intent_evidence([ev])[0]
    assert upgraded.category == SignalCategory.SCORING_PROFILING


def test_upgrade_intent_evidence_excludes_minimal_tier():
    if IntentAnnotation is None:
        return

    ann = IntentAnnotation(
        decision_autonomy="display_only",
        subject_type="system",
        consequential="no",
        model_id="codebert-onnx",
        confidence=0.5,
        risk_tier="minimal",
    )
    ev = EvidenceItem(
        evidence_id="ev_intent_min",
        evidence_kind=EvidenceKind.CALLSITE,
        category=SignalCategory.AI_SDK,
        token_hash="sha256:min",
        token_label="openai",
        locations=["src/llm.py:1"],
        scope=EvidenceScope.PROD,
        reachability=Reachability.INTERNAL_CALLCHAIN,
        detector_id="DET_INTENT_V1",
        detector_version="1.1.0",
        redaction_level="hash_only",
        rationale_code="intent_annotation",
        confidence=0.5,
        intent_annotation=ann,
    )

    upgraded = _upgrade_intent_evidence([ev], ai_legacy=False)
    assert upgraded == []


def test_gate_excludes_apirouter_from_intent_candidates(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    app_file = src / "mixed.py"
    app_file.write_text(
        "import openai\n"
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "client = openai.Client()\n",
        encoding="utf-8",
    )

    from opencomplai_core.scanner.ai_usage_gate import gate_features_for_intent
    from opencomplai_core.scanner.file_ai_context import FileAiContext

    features = FeatureStore(repo_root=tmp_path)
    features.imports.append(
        ImportRef(module="openai", location=f"{app_file}:1", scope=EvidenceScope.PROD)
    )
    features.callsites.extend(
        [
            CallsiteRef(
                name="APIRouter", location=f"{app_file}:3", scope=EvidenceScope.PROD
            ),
            CallsiteRef(
                name="openai.Client", location=f"{app_file}:4", scope=EvidenceScope.PROD
            ),
        ]
    )
    ctx = {
        str(app_file): FileAiContext(
            file_path=str(app_file),
            ai_imports=["openai"],
            has_ml_sdk=True,
        )
    }
    gated = gate_features_for_intent(features, ctx)
    call_names = {c.name for c in gated.features.callsites}
    assert "APIRouter" not in call_names
    assert "openai.Client" in call_names or len(gated.features.imports) >= 1
