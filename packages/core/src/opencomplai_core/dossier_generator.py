"""
Annex IV dossier generator.

Builds a complete AnnexIVDossier from a system manifest and risk assessment
result. Computes and sets the bundle_checksum. The Article 12 record-keeping
block states only what the manifest declares. Signing is Ed25519 only
(DOSSIER_SIGNING_KEY_PATH or SIGNING_KEY_PRIVATE); otherwise the dossier is
labelled unsigned. LOCAL_SIGNING_KEY_PATH no longer signs dossiers.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
import warnings
from datetime import UTC, datetime
from pathlib import Path

from opencomplai_core.dossier import (
    PROVIDER_SUPPLIED_PLACEHOLDER,
    AnnexIVDossier,
    AnnexIVSection1,
    AnnexIVSection2,
    AnnexIVSection3,
    AnnexIVSection4,
    AnnexIVSection5,
    AnnexIVSection6,
    AnnexIVSection7,
    AnnexIVSection8,
    AnnexIVSection9,
    ArticleTwelveRecordKeeping,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    CorroborationReport,
    GapStatus,
    HumanOversight,
    RiskResult,
    SystemManifest,
)
from opencomplai_core.rules import RULE_SET_VERSION

__all__ = [
    "BUNDLE_EXCLUDE",
    "RECORD_KEEPING_REVIEW_NOTE",
    "generate_dossier",
    "record_keeping_gap_status",
]

#: Fields left out of the bundle checksum and the signed bytes: envelope
#: metadata and derived fields that are not document content. Shared with
#: `dossier_verify` so generation and verification cannot disagree.
BUNDLE_EXCLUDE = frozenset(
    {
        "dossier_id",
        "generated_at",
        "bundle_checksum",
        "signature",
        "signature_status",
        "section2_complete",  # derived from section2 content
    }
)

#: Lawyer-packet line for the Art. 12 declaration source (E-15).
RECORD_KEEPING_REVIEW_NOTE = {
    "source": "Regulation (EU) 2024/1689 Art. 12; manifest declaration",
    "confidence": "low",
    "needs_founder_review": True,
}


def _manifest_str(manifest: SystemManifest, field: str) -> str | None:
    """Read an optional provider-attestation field the manifest may not define."""
    value = getattr(manifest, field, None)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _manifest_list(manifest: SystemManifest, field: str) -> list[str]:
    value = getattr(manifest, field, None)
    return list(value) if isinstance(value, (list, tuple)) and value else []


def _declared_block(manifest: SystemManifest) -> dict | None:
    """The manifest's `record_keeping` block as a dict, or None when absent.

    The one reader of the block: dossier content and the gap status both go
    through here so there is a single interpretation of it.
    """
    block = getattr(manifest, "record_keeping", None)
    if block is None:
        return None
    if isinstance(block, dict):
        return block
    dump = getattr(block, "model_dump", None)
    return dump() if callable(dump) else None


def _declared_record_keeping(
    manifest: SystemManifest, ledger_root_hash: str | None
) -> ArticleTwelveRecordKeeping:
    """Art. 12 block from the manifest declaration only: absent means false."""
    block = _declared_block(manifest)
    if block is None:
        return ArticleTwelveRecordKeeping(ledger_root_hash=ledger_root_hash)
    days = block.get("log_retention_days")
    return ArticleTwelveRecordKeeping(
        logging_enabled=block.get("logging_enabled") is True,
        log_retention_days=days if type(days) is int and days >= 1 else None,
        evidence_vault_enabled=block.get("evidence_vault_enabled") is True,
        ledger_root_hash=ledger_root_hash,
        provider_supplied=True,
    )


def record_keeping_gap_status(manifest: SystemManifest) -> ArticleGapStatus | None:
    """Gap candidate for the Art. 12 declaration; None when nothing declared.

    A declaration is never verified here, so declared logging is PARTIAL at
    best, never MET.
    """
    if _declared_block(manifest) is None:
        return None
    declared = _declared_record_keeping(manifest, None)
    yes_no = ("no", "yes")
    return ArticleGapStatus(
        article="",
        status=GapStatus.PARTIAL if declared.logging_enabled else GapStatus.MISSING,
        source=ArticleGapSource.MANIFEST,
        evidence_ref="manifest:record_keeping_declaration",
        rationale=(
            "Record keeping declared in the manifest: logging enabled "
            f"{yes_no[declared.logging_enabled]}, retention declared "
            f"{yes_no[declared.log_retention_days is not None]}. A declaration "
            "only; not verified against the system."
        ),
        confidence=None,
        confidence_label=ConfidenceLabel.NOT_ASSESSED,
    )


#: Section 2's stub fallback, reused here so Section 4's honesty check can't
#: be satisfied by the same placeholder text that already marks Section 2
#: incomplete (D-7).
STUB_TEXT = "Not specified in this release."

#: Below this length a string reads as a placeholder word ("x", "n/a", "TBD")
#: rather than a real one-line attestation. Not a hard compliance threshold —
#: just enough to reject the trivial cases D-7 is about.
_MIN_ATTESTATION_TEXT_LENGTH = 10

#: "YYYY-MM-DD: <description>" — the documented free-text shape for a
#: lifecycle-change or post-market-monitoring entry (Annex IV pt.6/9).
_DATED_ENTRY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}:\s*(?P<description>\S.*)$")

#: "<standard id/name> — <one-line reason>" — the documented free-text shape
#: for a harmonised-standards entry (Annex IV pt.7) that isn't a catalogue-id
#: match. Dash must be space-separated so it isn't confused with a hyphen
#: inside the id itself (e.g. "ISO-9001").
_HARMONISED_STANDARD_PATTERN = re.compile(
    r"^(?P<ref>\S.*?)\s[-\u2013\u2014]\s(?P<reason>\S.*)$"
)


def _is_real_attestation_text(
    value: str | None, min_length: int = _MIN_ATTESTATION_TEXT_LENGTH
) -> bool:
    """Non-empty, long enough, and not the Section 2 stub — a real provider
    attestation rather than a placeholder string."""
    if not value:
        return False
    value = value.strip()
    return len(value) >= min_length and value != STUB_TEXT


def _is_dated_entry(value: str) -> bool:
    """Matches "YYYY-MM-DD: <description>" with a non-placeholder description."""
    match = _DATED_ENTRY_PATTERN.match(value.strip())
    if not match:
        return False
    return _is_real_attestation_text(match.group("description"))


def _harmonised_standards_catalogue_ids() -> frozenset[str] | None:
    """Best-effort load of the harmonised-standards catalogue.

    Returns None (not an empty set) when the catalogue module isn't
    available — it doesn't land until a later epic — so callers fall back to
    the documented free-text pattern instead of rejecting every entry.
    """
    try:
        from opencomplai_core.harmonised_standards import get_catalog
    except ImportError:
        return None
    try:
        return frozenset(get_catalog())
    except Exception:
        return None


def _harmonised_standards_full_catalogue() -> dict[str, object] | None:
    """Best-effort load of the full harmonised-standards catalogue (id ->
    entry, with `.articles_covered`). Same best-effort contract as
    `_harmonised_standards_catalogue_ids`."""
    try:
        from opencomplai_core.harmonised_standards import get_catalog
    except ImportError:
        return None
    try:
        return get_catalog()
    except Exception:
        return None


def _crosswalk_citation(article: str) -> str | None:
    """Best-effort framework-crosswalk citation for one EU AI Act article.

    Returns None when the crosswalk module isn't available (a later epic)
    or has no row for this article — never raises, mirroring the
    harmonised-standards best-effort lookups above (D-3a is a mapping
    citation, not a gate, so a missing/broken crosswalk must never block
    dossier generation).
    """
    try:
        from opencomplai_core.framework_crosswalk import get_crosswalk
    except ImportError:
        return None
    try:
        row = get_crosswalk().get(article)
    except Exception:
        return None
    if row is None:
        return None
    return (
        f"{article} -> ISO/IEC 42001:2023 {row.iso_42001_clause} "
        f"(mapped, confidence: {row.confidence}; framework crosswalk, "
        "not a computed conformity verdict)"
    )


def _is_recognised_harmonised_standard(entry: str) -> bool:
    """A harmonised-standards entry is honest when it matches a catalogue id
    (best-effort — see `_harmonised_standards_catalogue_ids`) or the
    documented free-text pattern "<standard id/name> — <one-line reason>".
    A bare arbitrary string (just a name, no matched id and no reason)
    matches neither.
    """
    entry = entry.strip()
    catalogue_ids = _harmonised_standards_catalogue_ids()
    if catalogue_ids is not None and entry in catalogue_ids:
        return True
    match = _HARMONISED_STANDARD_PATTERN.match(entry)
    if not match:
        return False
    return _is_real_attestation_text(match.group("reason"))


def _structured_oversight(manifest: SystemManifest) -> HumanOversight | None:
    """The manifest's structured oversight block, or None when absent or empty.

    Tolerates a manifest object without the attribute and a plain dict.
    """
    block = getattr(manifest, "human_oversight", None)
    if isinstance(block, dict):
        try:
            block = HumanOversight.model_validate(block)
        except ValueError:
            return None
    if block is None or not (block.roles or block.escalation or block.evidence_refs):
        return None
    return block


def _build_section3(manifest: SystemManifest) -> AnnexIVSection3:
    """Annex IV pt.3 — human oversight, monitoring approach, incident response.

    Counts as provider-supplied only when all three inputs are present: pt.3
    asks for oversight measures, monitoring approach, and incident response
    together, so a partially attested section must not pass the HIGH-risk gate.
    Oversight is present when the legacy list is non-empty or the structured
    block names at least one role; the block is copied verbatim and never
    folded into the legacy list.
    """
    oversight = _manifest_list(manifest, "human_oversight_measures")
    structured = _structured_oversight(manifest)
    monitoring = _manifest_str(manifest, "monitoring_approach")
    incident = _manifest_str(manifest, "incident_response_procedure")
    oversight_set = bool(oversight) or bool(structured and structured.roles)
    return AnnexIVSection3(
        human_oversight_measures=oversight,
        monitoring_approach=monitoring or PROVIDER_SUPPLIED_PLACEHOLDER,
        incident_response_procedure=incident or PROVIDER_SUPPLIED_PLACEHOLDER,
        provider_supplied=oversight_set and bool(monitoring) and bool(incident),
        human_oversight=structured,
    )


def _build_section6(manifest: SystemManifest) -> AnnexIVSection6:
    """Annex IV pt.6 — relevant changes through the system's lifecycle.

    A change-log reference alone is an honest attestation (it points at a
    real document); absent that, at least one change entry must be a dated,
    non-placeholder entry ("YYYY-MM-DD: <description>") — a bare arbitrary
    string does not count (D-7).
    """
    changes = _manifest_list(manifest, "lifecycle_changes")
    ref = _manifest_str(manifest, "change_log_reference")
    supplied = bool(ref) or any(_is_dated_entry(c) for c in changes)
    return AnnexIVSection6(
        changes=changes,
        change_log_reference=ref,
        note="" if supplied else PROVIDER_SUPPLIED_PLACEHOLDER,
        provider_supplied=supplied,
    )


def _warn_unmatched_harmonised_standards(standards: list[str]) -> None:
    """Warn (never fail) on a Section 7 entry that isn't a catalogue id.

    Silent when an entry matches a `harmonised_standards.py` catalogue id;
    a warning otherwise — free-text "alternative solutions" is a legitimate,
    separate field and is never checked here (CP-4 task 3). Best-effort: a
    catalogue load failure degrades to no warnings rather than blocking
    dossier generation.
    """
    catalogue_ids = _harmonised_standards_catalogue_ids()
    if catalogue_ids is None:
        return
    for entry in standards:
        entry = entry.strip()
        if entry and entry not in catalogue_ids:
            warnings.warn(
                f"Annex IV Section 7: harmonised_standards entry {entry!r} "
                "does not match a known harmonised-standards catalogue id.",
                stacklevel=2,
            )


def _build_section7(manifest: SystemManifest) -> AnnexIVSection7:
    """Annex IV pt.7 — harmonised standards applied, or alternative solutions.

    A standards entry must match a catalogue id or the documented free-text
    pattern; a free-text alternative-solutions rationale must be a real
    one-line justification, not a placeholder string (D-7). Separately, any
    entry that doesn't match a catalogue id emits a warning — not a hard
    fail — so a provider notices a typo'd or unrecognised standard id.
    """
    standards = _manifest_list(manifest, "harmonised_standards")
    alternative = _manifest_str(manifest, "alternative_solutions")
    supplied = any(_is_recognised_harmonised_standard(s) for s in standards) or (
        _is_real_attestation_text(alternative)
    )
    _warn_unmatched_harmonised_standards(standards)
    return AnnexIVSection7(
        harmonised_standards=standards,
        alternative_solutions=alternative,
        note="" if supplied else PROVIDER_SUPPLIED_PLACEHOLDER,
        provider_supplied=supplied,
        crosswalk_refs=_section7_crosswalk_refs(standards),
    )


def _section7_crosswalk_refs(standards: list[str]) -> list[str]:
    """Framework-crosswalk citations (D-3a) for the articles covered by any
    recognised (catalogue-id-matching) Section 7 harmonised standard.
    Best-effort and non-fatal, same contract as `_crosswalk_citation`."""
    catalogue = _harmonised_standards_full_catalogue()
    if catalogue is None:
        return []
    articles: list[str] = []
    for entry_id in standards:
        catalogue_entry = catalogue.get(entry_id.strip())
        if catalogue_entry is not None:
            for article in catalogue_entry.articles_covered:
                if article not in articles:
                    articles.append(article)
    refs = [_crosswalk_citation(a) for a in articles]
    return [r for r in refs if r is not None]


def _build_section8(manifest: SystemManifest) -> AnnexIVSection8:
    """Annex IV pt.8 — reference to the EU declaration of conformity (Art. 47).

    `declaration_sha256` is populated only alongside a `declaration_reference`
    — a hash with no reference to hash-check-against is meaningless.
    """
    ref = _manifest_str(manifest, "eu_declaration_of_conformity_ref")
    sha256 = _manifest_str(manifest, "eu_declaration_of_conformity_sha256")
    return AnnexIVSection8(
        declaration_reference=ref,
        declaration_sha256=sha256 if ref else None,
        note="" if ref else PROVIDER_SUPPLIED_PLACEHOLDER,
        provider_supplied=bool(ref),
    )


def _build_section9(manifest: SystemManifest) -> AnnexIVSection9:
    """Annex IV pt.9 — post-market monitoring plan (Art. 72).

    A monitoring-plan reference alone is an honest attestation; absent that,
    the summary must be a dated, non-placeholder entry — a bare arbitrary
    string does not count (D-7).
    """
    ref = _manifest_str(manifest, "post_market_monitoring_plan_ref")
    summary = _manifest_str(manifest, "post_market_monitoring_summary")
    supplied = bool(ref) or (summary is not None and _is_dated_entry(summary))
    return AnnexIVSection9(
        monitoring_plan_reference=ref,
        plan_summary=summary,
        note="" if supplied else PROVIDER_SUPPLIED_PLACEHOLDER,
        provider_supplied=supplied,
    )


def _performance_metrics_with_evals(
    base: dict[str, float], eval_report: object | None
) -> dict[str, float]:
    from opencomplai_core.models import EvalReport

    perf = dict(base)
    if isinstance(eval_report, EvalReport):
        for r in eval_report.results:
            perf[f"eval_{r.category.value}_score"] = r.score
    return perf


def generate_dossier(
    manifest: SystemManifest,
    risk_result: RiskResult,
    evidence_hashes: list[str] | None = None,
    ledger_root_hash: str | None = None,
    provider_name: str = "Unknown Provider",
    eval_report: object | None = None,
    corroboration_report: CorroborationReport | None = None,
) -> AnnexIVDossier:
    """
    Generate an Annex IV dossier from a system manifest and risk result.

    Args:
        manifest: The system manifest describing the AI system.
            `manifest.high_risk_presumption` is consulted here: a
            provider-declared presumption of high risk gates Section 2 /
            Annex IV completeness the same as a genuine "high" classification,
            even when `risk_result.risk_level` came back lower.
        risk_result: The risk assessment result from the risk engine.
        evidence_hashes: SHA-256 hashes of evidence objects in the vault.
        ledger_root_hash: Current Merkle root of the evidence ledger.
        provider_name: Name of the AI system provider.

    Returns:
        AnnexIVDossier with all sections populated and bundle_checksum set.
    """
    dossier_id = str(uuid.uuid4())
    generated_at = datetime.now(UTC).isoformat()

    from opencomplai_core.evaluators.registry import EVAL_SET_VERSION
    from opencomplai_core.models import EvalReport

    failed_rule_ids = [r.rule_id for r in risk_result.rule_results if not r.passed]
    eval_evidence_hashes: list[str] = []
    eval_overall: str | None = None
    eval_set_version: str | None = None
    if isinstance(eval_report, EvalReport):
        eval_set_version = eval_report.eval_set_version
        eval_overall = eval_report.overall_outcome.value
        eval_evidence_hashes = [r.evidence_hash for r in eval_report.results]
        for r in eval_report.results:
            if r.outcome.value == "fail":
                failed_rule_ids.append(r.evaluator_id)

    rationale = json.dumps(
        [{"rule_id": r.rule_id, "passed": r.passed} for r in risk_result.rule_results],
        sort_keys=True,
    )
    rationale_hash = f"sha256:{hashlib.sha256(rationale.encode()).hexdigest()}"

    # Determine whether Section 2 is substantively complete.
    # Required meaningful fields: training_data_description AND model_architecture.
    # A field is considered "stub" when it was not supplied by the manifest and
    # falls back to the placeholder string set in the generator.
    _section2_training_complete = bool(
        manifest.training_data_description
        and manifest.training_data_description != STUB_TEXT
    )
    _section2_arch_complete = bool(
        manifest.model_architecture and manifest.model_architecture != STUB_TEXT
    )
    # A provider-declared high_risk_presumption gates completeness the same
    # as a genuine "high" classification from assess() — the presumption
    # exists precisely so a declared-high-risk system can't slip through as
    # complete just because its intended_purpose text doesn't keyword-match
    # any Annex III rule. It never *downgrades* a rules-derived classification
    # (e.g. "unacceptable" stays ungated by this flag, same as before).
    _is_high_risk = (
        risk_result.risk_level.value == "high" or manifest.high_risk_presumption
    )
    # section2_complete is False only when high-risk AND at least one required
    # field is missing/stub.  For non-high-risk systems stubs are acceptable.
    section2_complete = not _is_high_risk or (
        _section2_training_complete and _section2_arch_complete
    )

    # Annex IV point 3 and points 6-9 are provider attestations. For a
    # HIGH-risk system a placeholder in any of them means the file is not a
    # complete Annex IV dossier, and must not be presented as one.
    section3 = _build_section3(manifest)
    _sections_6_9 = (
        _build_section6(manifest),
        _build_section7(manifest),
        _build_section8(manifest),
        _build_section9(manifest),
    )
    annex_iv_complete = not _is_high_risk or (
        section3.provider_supplied
        and all(section.provider_supplied for section in _sections_6_9)
    )

    dossier = AnnexIVDossier(
        dossier_id=dossier_id,
        system_id=manifest.system_id,
        commit_ref=manifest.commit_ref,
        generated_at=generated_at,
        compliance_target=manifest.compliance_target,
        section2_complete=section2_complete,
        rule_version=RULE_SET_VERSION,
        assessed_against="Reg. (EU) 2024/1689",
        scope_disclaimer=(
            "This assessment was generated by Opencomplai (rule-based, deterministic engine). "
            "It constitutes structured evidence, not legal advice. "
            f"Assessment against Reg. (EU) 2024/1689. "
            f"Rule set version: {RULE_SET_VERSION}. "
            "Generation timestamp is recorded in generated_at."
        ),
        section1=AnnexIVSection1(
            system_name=manifest.system_id,
            system_version=manifest.commit_ref,
            provider_name=provider_name,
            intended_purpose=manifest.intended_purpose,
            compliance_target=manifest.compliance_target,
            risk_class=risk_result.risk_level.value,
            deployment_context="production",
        ),
        section2=AnnexIVSection2(
            training_data_description=(
                manifest.training_data_description or "Not specified in this release."
            ),
            model_architecture=(
                manifest.model_architecture or "Not specified in this release."
            ),
            performance_metrics=_performance_metrics_with_evals(
                manifest.performance_metrics, eval_report
            ),
            known_limitations=list(manifest.known_limitations),
        ),
        section3=section3,
        section4=AnnexIVSection4(
            metrics_reported=_performance_metrics_with_evals(
                manifest.performance_metrics, eval_report
            ),
            appropriateness_rationale=_manifest_str(
                manifest, "metrics_appropriateness_rationale"
            )
            or PROVIDER_SUPPLIED_PLACEHOLDER,
            known_metric_limitations=list(manifest.known_limitations),
            # A real justification, not just a non-empty string and not the
            # Section 2 stub text (D-7).
            provider_supplied=_is_real_attestation_text(
                _manifest_str(manifest, "metrics_appropriateness_rationale")
            ),
        ),
        record_keeping=_declared_record_keeping(manifest, ledger_root_hash),
        agent_inventory=getattr(manifest, "agent_inventory", None),
        section6=_build_section6(manifest),
        section7=_build_section7(manifest),
        section8=_build_section8(manifest),
        section9=_build_section9(manifest),
        annex_iv_complete=annex_iv_complete,
        section5=AnnexIVSection5(
            risk_assessment_id=f"ra_{rationale_hash[7:15]}",
            risk_level=risk_result.risk_level.value,
            rules_evaluated=risk_result.rules_evaluated,
            rules_passed=risk_result.rules_passed,
            rules_failed=risk_result.rules_failed,
            failed_rule_ids=failed_rule_ids,
            rationale_hash=rationale_hash,
            eval_set_version=eval_set_version or EVAL_SET_VERSION,
            eval_overall_outcome=eval_overall,
            eval_evidence_hashes=eval_evidence_hashes,
            scanner_version=(
                corroboration_report.scanner_version if corroboration_report else None
            ),
            corroboration_detected_categories=(
                corroboration_report.detected_categories if corroboration_report else []
            ),
            corroboration_discrepancies=(
                corroboration_report.discrepancies if corroboration_report else []
            ),
            corroboration_severity=(
                corroboration_report.severity.value if corroboration_report else None
            ),
            corroboration_review_status=None,
            corroboration_baseline_ref=(
                corroboration_report.baseline_ref if corroboration_report else None
            ),
            corroboration_report_hash=(
                corroboration_report.report_hash if corroboration_report else None
            ),
            crosswalk_refs=[
                ref for ref in [_crosswalk_citation("Art. 9")] if ref is not None
            ],
        ),
        evidence_hashes=(evidence_hashes or []) + eval_evidence_hashes,
    )

    # Compute bundle checksum over deterministic content only (BUNDLE_EXCLUDE
    # drops envelope metadata and derived fields).
    bundle_json = dossier.model_dump_json(exclude=BUNDLE_EXCLUDE)
    bundle_checksum = f"sha256:{hashlib.sha256(bundle_json.encode()).hexdigest()}"
    dossier.bundle_checksum = bundle_checksum

    # Ed25519 or unsigned; there is no symmetric fallback. The key is
    # DOSSIER_SIGNING_KEY_PATH or SIGNING_KEY_PRIVATE (see signing.resolve_key).
    ed25519_key_path = os.environ.get("DOSSIER_SIGNING_KEY_PATH")
    if ed25519_key_path or os.environ.get("SIGNING_KEY_PRIVATE"):
        signature = _sign_bundle_ed25519(bundle_json, ed25519_key_path)
        if signature is not None:
            dossier.signature = signature
            dossier.signature_status = "ed25519"
    if dossier.signature is None and os.environ.get("LOCAL_SIGNING_KEY_PATH"):
        warnings.warn(
            "LOCAL_SIGNING_KEY_PATH is no longer used for dossiers; the dossier "
            "is unsigned. Set DOSSIER_SIGNING_KEY_PATH or SIGNING_KEY_PRIVATE "
            "for an Ed25519 signature.",
            stacklevel=2,
        )

    return dossier


def _sign_bundle_ed25519(bundle_json: str, key_path: str | None) -> str | None:
    """
    Sign the dossier bundle JSON with an Ed25519 key.

    Returns the base64 signature, or None (with a warning) on any failure.
    The warning names the error type only, never key material or key content.
    """
    try:
        from opencomplai_core.signing import SigningDomain, sign_bundle_bytes

        return sign_bundle_bytes(
            bundle_json.encode("utf-8"),
            Path(key_path or ""),
            SigningDomain.DOSSIER_BUNDLE,
        )
    except Exception as exc:
        warnings.warn(
            f"Dossier signing failed ({type(exc).__name__}); the dossier is unsigned.",
            stacklevel=3,
        )
        return None
