"""
Rule registry and base rule interface.

Rules are deterministic: the same input always produces the same RuleResult.
The RULE_REGISTRY list is the authoritative set of rules evaluated by the engine.
Add new rules by subclassing BaseRule and appending to RULE_REGISTRY.

Phase 10 adds:
  - AnnexIIIClassifierRule (REQ-RISK-001)
  - ProfilingDetectionRule (REQ-RISK-002)
  - SubstantialModificationRule (REQ-RISK-003)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from opencomplai_core.models import AssessmentInput, RuleResult


class BaseRule(ABC):
    """Base class for all assessment rules."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique rule identifier, e.g. EU_AIA_ART6_HIGH_RISK."""
        ...

    @property
    @abstractmethod
    def rule_name(self) -> str:
        """Human-readable rule name."""
        ...

    @property
    @abstractmethod
    def reference(self) -> str:
        """EU AI Act article or clause reference."""
        ...

    @abstractmethod
    def evaluate(self, input: AssessmentInput) -> RuleResult:
        """Evaluate the rule against the given input and return a RuleResult."""
        ...


ANNEX_III_CATEGORIES: dict[str, frozenset[str]] = {
    "biometric": frozenset(
        [
            "biometric identification",
            "biometric categorisation",
            "facial recognition",
            "gait recognition",
            "voice recognition",
            "fingerprint",
            "iris recognition",
            "remote biometric",
        ]
    ),
    "critical_infrastructure": frozenset(
        [
            "critical infrastructure",
            "water supply",
            "gas supply",
            "electricity grid",
            "transport infrastructure",
            "road traffic",
            "railway",
            "digital infrastructure",
        ]
    ),
    "education": frozenset(
        [
            "education",
            "vocational training",
            "student assessment",
            "exam proctoring",
            "proctoring",
            "admissions",
            "educational institution",
            "learning outcome",
        ]
    ),
    "employment": frozenset(
        [
            "employment",
            "recruitment",
            "hiring",
            "screening candidates",
            "employment screening",
            "worker management",
            "performance evaluation",
            "promotion decision",
            "task allocation",
            "monitoring workers",
            "monitoring worker",
            "worker productivity",
        ]
    ),
    "essential_services": frozenset(
        [
            "essential services",
            "social benefits",
            "credit scoring",
            "creditworthiness",
            "insurance pricing",
            "insurance premium pricing",
            "health services",
            "emergency services",
            "public services",
        ]
    ),
    "law_enforcement": frozenset(
        [
            "law enforcement",
            "crime prediction",
            "predictive policing",
            "criminal justice",
            "polygraph",
            "risk assessment criminal",
            "crime risk assessment",
            "profiling suspects",
            "evidence reliability",
        ]
    ),
    "migration": frozenset(
        [
            "migration",
            "asylum",
            "border control",
            "visa assessment",
            "visa application",
            "immigration",
            "refugee",
            "border management",
        ]
    ),
    "justice": frozenset(
        [
            "justice",
            "judicial",
            "court decision",
            "democratic process",
            "election",
            "voting",
            "legal interpretation",
            "legal outcome prediction",
            "outcome prediction",
        ]
    ),
}

UNACCEPTABLE_RISK_SIGNALS: frozenset[str] = frozenset(
    [
        "subliminal manipulation",
        "exploiting vulnerabilities",
        "social scoring",
        "social credit",
        "real-time remote biometric surveillance",
        "real-time biometric public space",
    ]
)


class AnnexIIIClassifierRule(BaseRule):
    rule_id = "EU_AIA_ART6_HIGH_RISK"
    rule_name = "High-Risk System Classification (Article 6 / Annex III)"
    reference = "EU AI Act, Article 6, Annex III"

    def evaluate(self, input: AssessmentInput) -> RuleResult:
        use_case = input.model.use_case.lower()
        matched_categories: list[str] = []

        for category, keywords in ANNEX_III_CATEGORIES.items():
            if any(kw in use_case for kw in keywords):
                matched_categories.append(category)

        is_high_risk = len(matched_categories) > 0

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=not is_high_risk,
            rationale=(
                f"Use case '{input.model.use_case}' matches Annex III categories: "
                f"{', '.join(matched_categories)}."
                if is_high_risk
                else f"Use case '{input.model.use_case}' does not match any "
                f"Annex III high-risk categories."
            ),
            reference=self.reference,
        )


class UnacceptableRiskRule(BaseRule):
    rule_id = "EU_AIA_ART5_UNACCEPTABLE"
    rule_name = "Prohibited AI Practice Detection (Article 5)"
    reference = "EU AI Act, Article 5"

    def evaluate(self, input: AssessmentInput) -> RuleResult:
        use_case = input.model.use_case.lower()
        matched = [s for s in UNACCEPTABLE_RISK_SIGNALS if s in use_case]
        is_unacceptable = len(matched) > 0

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=not is_unacceptable,
            rationale=(
                f"Use case '{input.model.use_case}' contains prohibited practice signals: "
                f"{', '.join(matched)}. This use case is prohibited under EU AI Act Article 5."
                if is_unacceptable
                else f"No prohibited practice signals detected in '{input.model.use_case}'."
            ),
            reference=self.reference,
        )


class ProfilingDetectionRule(BaseRule):
    rule_id = "EU_AIA_ART6_PROFILING"
    rule_name = "Profiling Detection — Force High-Risk (Article 6(3))"
    reference = "EU AI Act, Article 6(3), Recital 34"

    PROFILING_SIGNALS: frozenset[str] = frozenset(
        [
            "profiling",
            "profile natural persons",
            "behavioural profiling",
            "personality profiling",
            "automated profiling",
        ]
    )

    def evaluate(self, input: AssessmentInput) -> RuleResult:
        if input.answers.get("profiling_detected") is True:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                rationale=(
                    "Profiling explicitly declared in assessment answers. "
                    "System is classified as high-risk per Article 6(3)."
                ),
                reference=self.reference,
            )

        use_case = input.model.use_case.lower()
        matched = [s for s in self.PROFILING_SIGNALS if s in use_case]

        if matched:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                rationale=(
                    f"Profiling signals detected in use case: {', '.join(matched)}. "
                    f"System is classified as high-risk per Article 6(3)."
                ),
                reference=self.reference,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=True,
            rationale="No profiling signals detected in use case or answers.",
            reference=self.reference,
        )


class SubstantialModificationRule(BaseRule):
    rule_id = "EU_AIA_ART25_MODIFICATION_TRAP"
    rule_name = "Substantial Modification Trap (Article 25 / Article 3(23))"
    reference = "EU AI Act, Article 25, Article 3(23), Recital 66"

    def evaluate(self, input: AssessmentInput) -> RuleResult:
        is_modified = input.answers.get("substantial_modification", False)

        if is_modified:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                rationale=(
                    "Substantial modification detected. A new conformity assessment is required "
                    "before this system can be re-deployed. Deployment is frozen until HITL "
                    "approval is obtained. (TRAP_DETECTED — exit code 4)"
                ),
                reference=self.reference,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=True,
            rationale="No substantial modification declared in assessment answers.",
            reference=self.reference,
        )


RULE_REGISTRY: list[BaseRule] = [
    UnacceptableRiskRule(),
    AnnexIIIClassifierRule(),
    ProfilingDetectionRule(),
    SubstantialModificationRule(),
]

# Monotonically incrementing version for the rule set.
# Bump when any rule logic, keyword list, or reference changes.
# Every generated dossier references this version for Annex IV traceability
# per EU AI Act Art. 11 and post-market monitoring (Art. 72).
RULE_SET_VERSION = "1.0.0"
