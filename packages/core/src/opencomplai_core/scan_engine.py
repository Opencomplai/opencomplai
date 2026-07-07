"""Code corroboration scan engine — runs all registered detectors."""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from opencomplai_core.models import (
    CorroborationReport,
    DetectionFinding,
    DiscrepancySeverity,
    EvidenceItem,
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
from opencomplai_core.scanner.feature_types import FeatureStore, ScanProgressCallback
from opencomplai_core.scanner.features import ScanConfig, extract_features
from opencomplai_core.scanner.fusion import fuse_evidence
from opencomplai_core.scanner.inventory import build_repo_inventory
from opencomplai_core.scanner.mapping import derive_declared_categories
from opencomplai_core.scanner.ocignore import config_dict_for_hash, load_ocignore
from opencomplai_core.scanner.registry import DETECTOR_REGISTRY

if TYPE_CHECKING:
    from opencomplai_core.models import EuAiScanSummary


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
        from opencomplai_ai.config import get_active_model
        from opencomplai_ai.detector import IntentDetector

        resolved_model = model_id or get_active_model()
        return IntentDetector(resolved_model)
    except ImportError:
        return None


def _filter_features_to_detected_files(
    features: FeatureStore,
    evidence: list[EvidenceItem],
) -> FeatureStore:
    """Narrow callsites/imports to files that already have lexical findings,
    plus files with knowledge-pack code signals or known AI-library imports.
    """
    from dataclasses import replace

    from opencomplai_core.scanner.detectors._signals import match_token_identifier

    detected_files = {loc.rpartition(":")[0] for e in evidence for loc in e.locations}

    try:
        from opencomplai_ai.knowledge.annex_iii import all_code_signals

        code_signals = all_code_signals()
    except ImportError:
        code_signals = set()

    ai_library_categories = ("ai_sdks", "ml_frameworks", "orchestration")

    def _file_of(ref) -> str:
        return ref.location.rpartition(":")[0]

    def _token(ref) -> str:
        return (getattr(ref, "name", None) or getattr(ref, "module", "") or "").lower()

    def _matches_code_signal(ref) -> bool:
        from opencomplai_core.scanner.detectors._signals import match_any_code_signal

        tok = _token(ref)
        return match_any_code_signal(tok, code_signals) is not None

    def _matches_ai_library(ref) -> bool:
        tok = _token(ref)
        if not tok:
            return False
        return any(
            match_token_identifier(tok, cat) is not None
            for cat in ai_library_categories
        )

    signal_files = {
        _file_of(ref)
        for ref in (*features.imports, *features.callsites)
        if _matches_code_signal(ref) or _matches_ai_library(ref)
    }
    included_files = detected_files | signal_files

    if not included_files and not code_signals:
        return features

    return replace(
        features,
        callsites=[c for c in features.callsites if _file_of(c) in included_files],
        imports=[imp for imp in features.imports if _file_of(imp) in included_files],
    )


def _upgrade_intent_evidence(
    intent_evidence: list[EvidenceItem],
    *,
    ai_legacy: bool = False,
) -> list[EvidenceItem]:
    """Post-process intent evidence items before fusion.

    Only regulatory tiers (prohibited, high_risk, limited_risk) contribute to
    category upgrades and discrepancy detection. Minimal-tier items are excluded.
    """
    try:
        from opencomplai_ai.models import (
            _AREA_TO_SIGNAL_CATEGORY,
            REGULATORY_RISK_TIERS,
        )

        from opencomplai_core.models import SignalCategory
    except ImportError:
        return intent_evidence

    upgraded: list[EvidenceItem] = []
    for ev in intent_evidence:
        ann = getattr(ev, "intent_annotation", None)
        if ann is None:
            upgraded.append(ev)
            continue

        tier = getattr(ann, "risk_tier", "minimal")
        if not ai_legacy and tier not in REGULATORY_RISK_TIERS:
            continue

        area = getattr(ann, "annex_iii_area", None)
        art6_3 = getattr(ann, "art6_3_profiling", False)

        new_category = ev.category
        if area is not None:
            cat_name = _AREA_TO_SIGNAL_CATEGORY.get(area)
            if cat_name:
                new_category = getattr(SignalCategory, cat_name)
        if art6_3 and new_category not in (
            SignalCategory.BIOMETRIC,
            SignalCategory.SCORING_PROFILING,
        ):
            new_category = SignalCategory.SCORING_PROFILING

        if new_category != ev.category:
            ev = ev.model_copy(update={"category": new_category})
        upgraded.append(ev)
    return upgraded


def _build_eu_ai_scan_summary(
    usage_matches: dict,
    regulatory_evidence: list[EvidenceItem],
    *,
    declared_purpose: str = "",
) -> EuAiScanSummary:
    from opencomplai_core.models import (
        EuAiRegulatoryFinding,
        EuAiScanSummary,
        EuAiUsageEntry,
    )

    try:
        from opencomplai_ai.rationale import build_flag_rationale
    except ImportError:
        build_flag_rationale = None  # type: ignore[assignment,misc]

    capabilities: list[EuAiUsageEntry] = []
    for location, match in usage_matches.items():
        file_path = location.rpartition(":")[0]
        capabilities.append(
            EuAiUsageEntry(
                location=location,
                function=match.token,
                usage_type=match.usage_type.value,
                file=file_path,
            )
        )

    prohibited: list[EuAiRegulatoryFinding] = []
    high_risk: list[EuAiRegulatoryFinding] = []
    limited: list[EuAiRegulatoryFinding] = []

    for ev in regulatory_evidence:
        ann = ev.intent_annotation
        if ann is None:
            continue
        loc = ev.locations[0] if ev.locations else ""
        gate_reason = None
        usage = usage_matches.get(loc)
        if usage is not None:
            gate_reason = usage.reason
        rationale = None
        if build_flag_rationale is not None:
            rationale = build_flag_rationale(
                ann,
                gate_reason=gate_reason,
                declared_purpose=declared_purpose,
            )
        finding = EuAiRegulatoryFinding(
            location=loc,
            function=ev.token_label,
            risk_tier=ann.risk_tier,
            annex_iii_area=ann.annex_iii_area,
            eu_obligation=list(ann.eu_obligation),
            explanation=ann.explanation or (rationale.summary if rationale else None),
            needed_action=(
                ann.needed_action or (rationale.needed_action if rationale else None)
            ),
            rationale=rationale,
        )
        if ann.risk_tier == "prohibited":
            prohibited.append(finding)
        elif ann.risk_tier == "high_risk":
            high_risk.append(finding)
        elif ann.risk_tier == "limited_risk":
            limited.append(finding)

    return EuAiScanSummary(
        capabilities=capabilities,
        prohibited=prohibited,
        high_risk=high_risk,
        limited_risk=limited,
        gated_callsite_count=len(usage_matches),
        regulatory_finding_count=len(regulatory_evidence),
    )


def _suggest_repo_root_alternatives(repo_root: Path) -> list[str]:
    """Find nearby directories that may match a mistyped --repo-root."""
    import difflib

    target_name = repo_root.name.lower()
    if not target_name:
        return []

    search_roots: list[Path] = []
    for base in (Path.cwd(), repo_root.parent, Path.cwd().parent):
        resolved = base.resolve()
        if resolved not in search_roots:
            search_roots.append(resolved)

    candidates: dict[str, Path] = {}
    for base in search_roots:
        if not base.is_dir():
            continue
        try:
            for child in base.iterdir():
                if child.is_dir() and not child.name.startswith("."):
                    candidates.setdefault(child.name.lower(), child.resolve())
        except OSError:
            continue

    suggestions: list[str] = []
    for match in difflib.get_close_matches(
        target_name, list(candidates.keys()), n=5, cutoff=0.72
    ):
        path = candidates[match]
        suggestions.append(str(path))

    cwd = Path.cwd().resolve()
    filtered = [s for s in suggestions if Path(s).resolve() != cwd]
    return (filtered or suggestions)[:3]


_AUTO_CORRECT_MIN_SIMILARITY = 0.85


def validate_scan_repo_root(repo_root: Path, *, auto_correct: bool = False) -> Path:
    """Ensure repo-root exists and is a directory before scanning."""
    resolved = repo_root.resolve()
    if not resolved.exists():
        suggestions = _suggest_repo_root_alternatives(repo_root)
        if auto_correct and len(suggestions) == 1:
            import difflib

            candidate = Path(suggestions[0])
            ratio = difflib.SequenceMatcher(
                None, repo_root.name.lower(), candidate.name.lower()
            ).ratio()
            if ratio >= _AUTO_CORRECT_MIN_SIMILARITY:
                return candidate.resolve()

        message = (
            f"repo-root does not exist: {resolved}. "
            "Check --repo-root points at your project directory."
        )
        if suggestions:
            hint = "; ".join(suggestions)
            message += f" Did you mean: {hint}?"
        raise FileNotFoundError(message)
    if not resolved.is_dir():
        raise NotADirectoryError(
            f"repo-root is not a directory: {resolved}. "
            "Pass the folder that contains your source code."
        )
    return resolved


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
    ai_deep: bool = False,
    ai_legacy: bool = False,
) -> CorroborationReport:
    _start = time.monotonic()
    config = config or ScanConfig()
    repo_root = validate_scan_repo_root(repo_root)
    ocignore = load_ocignore(repo_root, config.ocignore_path)
    patterns = list(ocignore.patterns)
    if config.excludes:
        for name in config.excludes:
            if name not in patterns:
                patterns.append(name)
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
    if not inventory.entries:
        inventory.warnings.insert(
            0,
            f"empty_inventory: no files found under {repo_root.resolve()}. "
            "Verify --repo-root path (typo?), permissions, and .ocignore exclusions.",
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

    eu_ai_scan = None

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
                from opencomplai_core.scanner.ai_usage_gate import (
                    gate_features_for_intent,
                )
                from opencomplai_core.scanner.file_ai_context import (
                    build_file_ai_context_map,
                )
                from opencomplai_core.scanner.snippet_cache import SnippetCache

                snippet_cache = SnippetCache()
                file_contexts = build_file_ai_context_map(features, evidence)

                if ai_legacy:
                    candidate = features
                    usage_matches: dict = {}
                else:
                    prefiltered = (
                        features
                        if ai_deep
                        else _filter_features_to_detected_files(features, evidence)
                    )
                    gated = gate_features_for_intent(
                        prefiltered,
                        file_contexts,
                        snippet_cache=snippet_cache,
                    )
                    candidate = gated.features
                    usage_matches = gated.usage_matches

                n_callsites = len(candidate.callsites) + len(candidate.imports)
                if progress_cb and n_callsites > 0:
                    progress_cb.on_phase("ai_intent", n_callsites)

                intent_evidence = intent_detector.detect(
                    candidate,
                    progress_cb=progress_cb,
                    declared_purpose=declared_purpose,
                    usage_matches=usage_matches if not ai_legacy else None,
                    ai_legacy=ai_legacy,
                )
                intent_evidence = _upgrade_intent_evidence(
                    intent_evidence, ai_legacy=ai_legacy
                )

                if not ai_legacy:
                    eu_ai_scan = _build_eu_ai_scan_summary(
                        usage_matches,
                        intent_evidence,
                        declared_purpose=declared_purpose,
                    )
                    # EU AI Act mode: evidence contains regulatory intent findings only
                    evidence = sorted(
                        intent_evidence,
                        key=lambda e: (e.detector_id, e.token_label, e.locations[0]),
                    )
                else:
                    evidence = sorted(
                        [*evidence, *intent_evidence],
                        key=lambda e: (e.detector_id, e.token_label, e.locations[0]),
                    )
            except Exception as exc:
                import warnings

                warnings.warn(
                    f"AI intent analysis failed ({type(exc).__name__}: {exc}). "
                    "Scan results are unaffected; intent annotations were skipped.",
                    stacklevel=2,
                )

    findings = fuse_evidence(evidence)
    declared = derive_declared_categories(declared_purpose)
    relevant_findings = [
        f for f in findings if f.scope != EvidenceScope.DOCS or f.strength >= 0.5
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
        eu_ai_scan=eu_ai_scan,
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
