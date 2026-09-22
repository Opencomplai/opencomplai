"""
Annex IV Technical Documentation Dossier schema.

Defines the structure of the compliance dossier generated per release candidate.
Based on EU AI Act Article 11 and Annex IV requirements.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from opencomplai_core.models import ComplianceTarget


class AnnexIVSection1(BaseModel):
    """General description of the AI system (Annex IV, Section 1)."""

    system_name: str
    system_version: str
    provider_name: str
    intended_purpose: str
    compliance_target: ComplianceTarget
    risk_class: str
    deployment_context: str


class AnnexIVSection2(BaseModel):
    """Description of elements and development process (Annex IV, Section 2)."""

    training_data_description: str
    model_architecture: str
    performance_metrics: dict[str, float] = Field(default_factory=dict)
    known_limitations: list[str] = Field(default_factory=list)


#: Marker used by every section this engine cannot derive from the repository.
#: These are provider attestations, not artefacts a scanner can infer, so they
#: are emitted as explicit, labelled placeholders rather than silently omitted.
PROVIDER_SUPPLIED_PLACEHOLDER = (
    "Not supplied. This section requires a provider attestation and cannot be "
    "derived automatically from the repository."
)


class AnnexIVSection3(BaseModel):
    """Detailed information about monitoring, functioning and control (Annex IV, Section 3)."""

    human_oversight_measures: list[str] = Field(default_factory=list)
    monitoring_approach: str = PROVIDER_SUPPLIED_PLACEHOLDER
    incident_response_procedure: str = PROVIDER_SUPPLIED_PLACEHOLDER
    provider_supplied: bool = False


class AnnexIVSection4(BaseModel):
    """Appropriateness of the performance metrics (Annex IV, point 4).

    Annex IV point 4 asks the provider to justify *why* the chosen metrics are
    appropriate for the intended purpose. It is not a place for logging
    capability, which is an Article 12 record-keeping obligation — see
    `ArticleTwelveRecordKeeping`.
    """

    metrics_reported: dict[str, float] = Field(default_factory=dict)
    appropriateness_rationale: str = PROVIDER_SUPPLIED_PLACEHOLDER
    known_metric_limitations: list[str] = Field(default_factory=list)
    provider_supplied: bool = False


class ArticleTwelveRecordKeeping(BaseModel):
    """Automatic logging and record-keeping (Article 12).

    Was previously emitted as "Annex IV Section 4", which conflated two
    distinct obligations: Art. 12 requires high-risk systems to log
    automatically over their lifetime, while Annex IV point 4 concerns the
    appropriateness of performance metrics.
    """

    logging_enabled: bool
    log_retention_days: int
    evidence_vault_enabled: bool
    ledger_root_hash: str | None = None


class AnnexIVSection5(BaseModel):
    """Description of risk management system (Annex IV, Section 5)."""

    risk_assessment_id: str
    risk_level: str
    rules_evaluated: int
    rules_passed: int
    rules_failed: int
    failed_rule_ids: list[str] = Field(default_factory=list)
    rationale_hash: str
    eval_set_version: str | None = None
    eval_overall_outcome: str | None = None
    eval_evidence_hashes: list[str] = Field(default_factory=list)
    scanner_version: str | None = None
    corroboration_detected_categories: list[str] = Field(default_factory=list)
    corroboration_discrepancies: list[str] = Field(default_factory=list)
    corroboration_severity: str | None = None
    corroboration_review_status: str | None = None
    corroboration_baseline_ref: str | None = None
    corroboration_report_hash: str | None = None
    crosswalk_refs: list[str] = Field(
        default_factory=list,
        description=(
            "Framework-crosswalk citations for the risk-management article "
            "(Art. 9), e.g. an ISO/IEC 42001:2023 clause reference — mapped "
            "only, not a computed verdict (D-3a). Empty when no crosswalk "
            "row applies."
        ),
    )


class AnnexIVSection6(BaseModel):
    """Relevant changes made to the system through its lifecycle (Annex IV, point 6)."""

    changes: list[str] = Field(default_factory=list)
    change_log_reference: str | None = None
    note: str = PROVIDER_SUPPLIED_PLACEHOLDER
    provider_supplied: bool = False


class AnnexIVSection7(BaseModel):
    """Harmonised standards applied, or other solutions adopted (Annex IV, point 7)."""

    harmonised_standards: list[str] = Field(default_factory=list)
    alternative_solutions: str | None = None
    note: str = PROVIDER_SUPPLIED_PLACEHOLDER
    provider_supplied: bool = False
    crosswalk_refs: list[str] = Field(
        default_factory=list,
        description=(
            "Framework-crosswalk citations (ISO/IEC 42001:2023 clause) for "
            "each EU AI Act article the supplied harmonised standards cover "
            "— mapped only, not a computed verdict (D-3a). Empty when no "
            "crosswalk row applies."
        ),
    )


class AnnexIVSection8(BaseModel):
    """EU declaration of conformity (Annex IV, point 8; Article 47).

    Annex IV point 8 requires a *copy* of the declaration. This dossier records
    a reference to it — the declaration itself is a signed provider document
    that this engine neither holds nor can produce. `declaration_sha256` is
    the SHA-256 of that signed document as uploaded to the evidence vault, so
    a verifier can confirm the referenced file matches this dossier without
    the file itself being embedded here (see docs/src/concepts/annex-iv-coverage.md).
    """

    declaration_reference: str | None = None
    declaration_sha256: str | None = None
    note: str = PROVIDER_SUPPLIED_PLACEHOLDER
    provider_supplied: bool = False


class AnnexIVSection9(BaseModel):
    """Post-market monitoring plan (Annex IV, point 9; Article 72)."""

    monitoring_plan_reference: str | None = None
    plan_summary: str | None = None
    note: str = PROVIDER_SUPPLIED_PLACEHOLDER
    provider_supplied: bool = False


class AnnexIVDossier(BaseModel):
    """
    Annex IV technical documentation dossier (EU AI Act Article 11).

    Covers all nine Annex IV points. Points 1-5 are derived from the manifest,
    risk assessment, evaluators and scanner. Points 6-9 are provider
    attestations that cannot be inferred from a repository; they are emitted as
    explicit, labelled placeholders with `provider_supplied=False` until the
    provider fills them in. `annex_iv_complete` is False while any of them is
    still a placeholder on a HIGH-risk system — a dossier is not "complete
    Annex IV" merely because every field is present.

    This is the output of the Documentation Generator (REQ-DOC-001).
    In OSS mode: produced as a local bundle with a SHA-256 checksum.
    In Pro/Enterprise mode: signing is mandatory for badge issuance.
    """

    dossier_id: str = Field(..., description="UUID identifying this dossier")
    system_id: str
    commit_ref: str
    generated_at: str = Field(..., description="ISO 8601 timestamp")
    compliance_target: ComplianceTarget = ComplianceTarget.EU_AI_ACT

    section1: AnnexIVSection1
    section2: AnnexIVSection2
    section3: AnnexIVSection3
    section4: AnnexIVSection4
    section5: AnnexIVSection5
    section6: AnnexIVSection6 = Field(default_factory=AnnexIVSection6)
    section7: AnnexIVSection7 = Field(default_factory=AnnexIVSection7)
    section8: AnnexIVSection8 = Field(default_factory=AnnexIVSection8)
    section9: AnnexIVSection9 = Field(default_factory=AnnexIVSection9)

    # Article 12 record-keeping. Kept out of the numbered Annex IV sections
    # because it is a separate obligation; it was previously mislabelled as
    # Annex IV Section 4.
    record_keeping: ArticleTwelveRecordKeeping | None = None

    evidence_hashes: list[str] = Field(
        default_factory=list,
        description="SHA-256 hashes of evidence objects included in this dossier",
    )

    # OSS: None (unsigned). Pro/Enterprise: base64-encoded signature.
    signature: str | None = Field(
        None,
        description="Base64 signature. None in OSS unsigned mode.",
    )

    # Self-describing trust marker so an auditor cannot mistake an unsigned
    # OSS artifact for a Pro/Enterprise cryptographically-signed one.
    signature_status: str = Field(
        "unsigned",
        description=(
            "Trust level of this dossier: 'unsigned' (OSS default), "
            "'hmac-local' (HMAC fallback with a local key), "
            "or 'signed' (Pro/Enterprise asymmetric signing via HSM/KMS)."
        ),
    )

    bundle_checksum: str | None = Field(
        None,
        description="SHA-256 checksum of the serialised dossier bundle JSON.",
    )

    # EU AI Act Art. 11 / Annex IV traceability (Reg. (EU) 2024/1689)
    rule_version: str = Field(
        "1.0.0",
        description="Rule set version used for this assessment (RULE_SET_VERSION in rules.py).",
    )
    assessed_against: str = Field(
        "Reg. (EU) 2024/1689",
        description="Regulation or standard this dossier was assessed against.",
    )
    scope_disclaimer: str = Field(
        (
            "This assessment was generated by Opencomplai (rule-based, deterministic engine). "
            "It constitutes structured evidence, not legal advice. "
            "Assessment against Reg. (EU) 2024/1689."
        ),
        description=(
            "Mandatory scope disclaimer per EU AI Act Recital 27 / Art. 11. "
            "Must appear on all dossier outputs and dashboard views."
        ),
    )

    # HIGH-risk guardrail (Option B — soft warn): True when the manifest supplied
    # real content for every required Section 2 field (training_data_description
    # and model_architecture are mandatory; the rest are optional).  False when
    # either required field still contains the stub string "Not specified in this
    # release." and the system is classified as HIGH risk.  Auditors should treat
    # False as a conformity gap for any HIGH-risk deployment.
    section2_complete: bool = Field(
        True,
        description=(
            "False when the dossier was generated with stub Section 2 content "
            "for a HIGH-risk system. Auditors must not rely on Section 2 for "
            "conformity evidence when this field is False."
        ),
    )

    # Same guardrail as section2_complete, for the four provider-attestation
    # sections. Generating 5 of 9 sections and calling the result "Complete
    # Annex IV" is exactly the overstatement this flag exists to prevent.
    annex_iv_complete: bool = Field(
        True,
        description=(
            "False when a HIGH-risk dossier still carries placeholder content "
            "for any of Annex IV Sections 6-9 (lifecycle changes, harmonised "
            "standards, EU declaration of conformity, post-market monitoring "
            "plan). These require provider attestation and cannot be derived "
            "from the repository. Do not present such a dossier as a complete "
            "Annex IV technical documentation file."
        ),
    )


def validate_dossier_schema(
    dossier: AnnexIVDossier, presumed_high: bool = False
) -> bool:
    """
    Validate that a dossier contains all required Annex IV sections and fields.

    Returns True if the schema is complete (REQ-DOC-001).
    This is the validator used in the CI release gate.

    For a HIGH-risk system this requires all nine Annex IV points, including
    the provider attestations in Sections 6-9. It previously inspected only
    six Section 1 fields plus two hashes, so a dossier carrying 5 of 9 sections
    passed the release gate as complete.

    `presumed_high` mirrors the manifest's `high_risk_presumption` used by
    `generate_dossier` to compute `section2_complete`/`annex_iv_complete`: the
    dossier itself only carries the assess()-derived `section1.risk_class`,
    so a caller whose request was declared high-risk (but keyword-classified
    otherwise by assess()) must pass `presumed_high=True` here too, or this
    validator would skip the attestation checks below.
    """
    required_section1_fields = [
        "system_name",
        "system_version",
        "provider_name",
        "intended_purpose",
        "compliance_target",
        "risk_class",
    ]
    for field in required_section1_fields:
        if not getattr(dossier.section1, field, None):
            return False

    if not dossier.section5.rationale_hash:
        return False

    if not dossier.bundle_checksum:
        return False

    # Article 12 record-keeping must be present and enabled.
    if dossier.record_keeping is None:
        return False

    if dossier.section1.risk_class == "high" or presumed_high:
        # Every Annex IV point must be attested, not merely instantiated.
        for section in (
            dossier.section6,
            dossier.section7,
            dossier.section8,
            dossier.section9,
        ):
            if not section.provider_supplied:
                return False
        if not dossier.annex_iv_complete:
            return False
        if not dossier.section4.provider_supplied:
            return False
        if not dossier.section3.provider_supplied:
            return False

    return True
