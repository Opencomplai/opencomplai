"""Code corroboration scan engine — runs all registered detectors."""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from pathlib import Path

from opencomplai_core.models import (
    CorroborationReport,
    DetectionFinding,
    DiscrepancySeverity,
    EvidenceScope,
    Reachability,
    ScanSummary,
    ScoreBreakdown,
)
from opencomplai_core.scanner._hashing import report_hash as compute_report_hash
from opencomplai_core.scanner.cache import (
    FeatureCache,
    config_hash_from_dict,
    default_detector_versions,
)
from opencomplai_core.scanner.constants import SCANNER_VERSION
from opencomplai_core.scanner.feature_types import ScanProgressCallback
from opencomplai_core.scanner.features import ScanConfig, extract_features
from opencomplai_core.scanner.fusion import fuse_evidence
from opencomplai_core.scanner.inventory import build_repo_inventory
from opencomplai_core.scanner.ocignore import config_dict_for_hash, load_ocignore
from opencomplai_core.scanner.mapping import derive_declared_categories
from opencomplai_core.scanner.registry import DETECTOR_REGISTRY


def input_digest(repo_root: Path, commit_ref: str, config_hash: str) -> str:
    raw = f"{repo_root.resolve()}|{commit_ref}|{config_hash}|{SCANNER_VERSION}"
    return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()}"


def _scope_weight(scope: EvidenceScope) -> float:
    return {
        EvidenceScope.PROD: 1.0,
        EvidenceScope.TEST: 0.3,
        EvidenceScope.DEV: 0.25,
        EvidenceScope.DOCS: 0.15,
        EvidenceScope.GENERATED: 0.1,
        EvidenceScope.VENDOR: 0.1,
        EvidenceScope.UNKNOWN: 0.2,
    }.get(scope, 0.2)


def _reach_weight(reach: Reachability) -> float:
    return {
        Reachability.REACHABLE_ENTRYPOINT: 1.0,
        Reachability.INTERNAL_CALLCHAIN: 0.85,
        Reachability.IMPORT_ONLY: 0.4,
        Reachability.MANIFEST_ONLY: 0.25,
        Reachability.UNKNOWN: 0.2,
    }.get(reach, 0.2)


def score_findings(
    findings: list[DetectionFinding],
) -> dict[str, ScoreBreakdown]:
    scores: dict[str, ScoreBreakdown] = {}
    for f in findings:
        scope_w = _scope_weight(f.scope)
        reach_w = _reach_weight(f.reachability)
        tax_w = 1.0 if f.mapped_taxonomy else 0.5
        det_conf = min(1.0, f.strength / max(scope_w * reach_w, 0.01))
        final = min(1.0, det_conf * scope_w * reach_w * tax_w)
        scores[f.finding_id] = ScoreBreakdown(
            detector_confidence=round(det_conf, 4),
            evidence_strength=round(f.strength, 4),
            scope_weight=scope_w,
            reachability_weight=reach_w,
            taxonomy_weight=tax_w,
            final_score=round(final, 4),
            rationale_codes=f.confidence_rationale,
        )
    return scores


def classify_severity(
    discrepancies: list[str],
    findings: list[DetectionFinding],
    scores: dict[str, ScoreBreakdown],
) -> DiscrepancySeverity:
    if not discrepancies:
        return DiscrepancySeverity.NONE
    if "unacceptable" in discrepancies:
        prod_corroborated = any(
            "unacceptable" in f.mapped_taxonomy
            and f.scope == EvidenceScope.PROD
            and f.reachability
            in (Reachability.REACHABLE_ENTRYPOINT, Reachability.INTERNAL_CALLCHAIN)
            for f in findings
        )
        if prod_corroborated:
            return DiscrepancySeverity.CRITICAL

    major_candidates = [
        f
        for f in findings
        if f.mapped_taxonomy
        and any(t in discrepancies for t in f.mapped_taxonomy)
        and f.scope == EvidenceScope.PROD
        and f.reachability
        in (Reachability.REACHABLE_ENTRYPOINT, Reachability.INTERNAL_CALLCHAIN)
        and scores.get(
            f.finding_id,
            ScoreBreakdown(
                detector_confidence=0,
                evidence_strength=0,
                scope_weight=0,
                reachability_weight=0,
                taxonomy_weight=0,
                final_score=0,
                rationale_codes=[],
            ),
        ).final_score
        >= 0.4
    ]
    if major_candidates:
        return DiscrepancySeverity.MAJOR

    minor_candidates = [
        f for f in findings if any(t in discrepancies for t in f.mapped_taxonomy)
    ]
    if minor_candidates:
        return DiscrepancySeverity.MINOR
    return DiscrepancySeverity.INFO


def compare_to_declaration(
    detected: list[str],
    declared: list[str],
    baseline: list[str] | None = None,
) -> list[str]:
    declared_set = set(declared)
    baseline_set = set(baseline or [])
    return sorted(set(detected) - declared_set - baseline_set)


def run_detectors(
    features,
    registry=None,
    progress_cb: ScanProgressCallback | None = None,
) -> list:
    from opencomplai_core.models import EvidenceItem

    registry = registry or DETECTOR_REGISTRY
    if progress_cb:
        progress_cb.on_phase("detect", len(registry))
    evidence: list[EvidenceItem] = []
    for i, detector in enumerate(registry):
        try:
            evidence.extend(detector.detect(features))
        except Exception:
            continue
        if progress_cb:
            progress_cb.on_step("detect", i + 1, detector.detector_id)
    return evidence


def _load_intent_plugin(model_id: str | None = None):
    try:
        from opencomplai_ai.detector import IntentDetector
        from opencomplai_ai.config import get_active_model

        resolved_model = model_id or get_active_model()
        return IntentDetector(resolved_model)
    except ImportError:
        return None


def run_scan(
    system_id: str,
    commit_ref: str,
    repo_root: Path,
    declared_purpose: str,
    config: ScanConfig | None = None,
    baseline_ref: str | None = None,
    baseline_categories: list[str] | None = None,
    progress_cb: ScanProgressCallback | None = None,
    ai_intent: bool = False,
    ai_model: str | None = None,
) -> CorroborationReport:
    _start = time.monotonic()
    config = config or ScanConfig()
    ocignore = load_ocignore(repo_root, config.ocignore_path)
    patterns = list(ocignore.patterns)
    if config.excludes:
        for name in config.excludes:
            pat = name if name.endswith("/") else name
            if pat not in patterns:
                patterns.append(pat)
    limits = ocignore.limits
    config_dict = config_dict_for_hash(patterns, limits, ocignore.content_hash)
    config_dict["use_cache"] = config.use_cache
    cfg_hash = config_hash_from_dict(config_dict)

    inventory = build_repo_inventory(
        repo_root,
        limits,
        config.excludes,
        ignore_patterns=patterns,
        progress_cb=progress_cb,
    )
    cache = None
    if config.cache_dir and config.use_cache:
        cache = FeatureCache(
            cache_dir=config.cache_dir,
            config_hash=cfg_hash,
            detector_versions=default_detector_versions(),
        )
    features = extract_features(inventory, config, cache, progress_cb=progress_cb)
    evidence = sorted(
        run_detectors(features, progress_cb=progress_cb),
        key=lambda e: (e.detector_id, e.token_label, e.locations[0]),
    )

    if ai_intent:
        intent_detector = _load_intent_plugin(ai_model)
        if intent_detector is None:
            import warnings
            warnings.warn(
                "opencomplai-ai not installed — AI intent analysis skipped. "
                "Run: pip install opencomplai-ai",
                stacklevel=2,
            )
        else:
            try:
                intent_evidence = intent_detector.detect(features)
                evidence = sorted(
                    [*evidence, *intent_evidence],
                    key=lambda e: (e.detector_id, e.token_label, e.locations[0]),
                )
            except Exception:
                pass

    findings = fuse_evidence(evidence)
    declared = derive_declared_categories(declared_purpose)
    relevant_findings = [
        f
        for f in findings
        if f.scope != EvidenceScope.DOCS or f.strength >= 0.5
    ]
    detected = sorted({c for f in relevant_findings for c in f.mapped_taxonomy})
    discrepancies = compare_to_declaration(detected, declared, baseline_categories)
    scores = score_findings(findings)
    severity = classify_severity(discrepancies, findings, scores)

    digest = input_digest(repo_root, commit_ref, cfg_hash)
    scan_id = (
        f"scan_{hashlib.sha256(f'{digest}|{system_id}'.encode()).hexdigest()[:16]}"
    )
    detector_versions = default_detector_versions()
    cache_summary = cache.summary() if cache else {}

    report = CorroborationReport(
        scan_id=scan_id,
        system_id=system_id,
        commit_ref=commit_ref,
        scanner_version=SCANNER_VERSION,
        input_digest=digest,
        config_hash=cfg_hash,
        detector_versions=detector_versions,
        declared_purpose=declared_purpose,
        declared_categories=declared,
        evidence=evidence,
        findings=findings,
        detected_categories=detected,
        discrepancies=discrepancies,
        score_breakdown=scores,
        severity=severity,
        feature_summary=features.summary,
        cache_summary=cache_summary,
        skipped_paths=inventory.skipped_paths,
        skip_reasons=inventory.skip_reasons,
        limits_hit=inventory.limits_hit,
        warnings=inventory.warnings,
        detector_errors=[],
        baseline_ref=baseline_ref,
        generated_at=datetime.now(UTC).isoformat(),
        report_hash="",
    )
    report.report_hash = compute_report_hash(report)
    if progress_cb:
        progress_cb.on_done(
            elapsed_s=time.monotonic() - _start,
            file_count=len(inventory.entries),
            skip_reasons=inventory.skip_reasons,
            limits_hit=inventory.limits_hit,
        )
    return report


def scan_summary_from_report(report: CorroborationReport) -> ScanSummary:
    from opencomplai_core.scanner._hashing import evidence_item_hash

    return ScanSummary(
        scan_id=report.scan_id,
        scanner_version=report.scanner_version,
        severity=report.severity,
        detected_categories=report.detected_categories,
        discrepancies=report.discrepancies,
        report_hash=report.report_hash,
        evidence_hashes=[evidence_item_hash(e) for e in report.evidence],
    )
