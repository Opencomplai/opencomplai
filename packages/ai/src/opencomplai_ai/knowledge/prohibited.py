"""Art. 5 prohibited AI practices — machine-readable knowledge pack.

Source of truth: eu-ai-act/references/risk-classification.md (Art. 5 section).

All 9 prohibitions are listed.  The 9th (nudification / CSAM) applies from
2 Dec 2026 per the AI Omnibus; the original 8 from 2 Feb 2025.

Scanner components that detect prohibited practices import PROHIBITED and
match code signals / keywords against it before applying any Annex III
classification.  A prohibited match takes precedence over high-risk.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProhibitedEntry:
    article: str
    title: str
    keywords: tuple[str, ...]
    code_signals: tuple[str, ...]
    exceptions: tuple[str, ...]
    applies_from: str  # ISO date string


PROHIBITED: list[ProhibitedEntry] = [
    ProhibitedEntry(
        article="Art.5(1)(a)",
        title="Subliminal or manipulative AI techniques causing significant harm",
        keywords=(
            "subliminal manipulation",
            "dark pattern AI",
            "deceptive AI",
            "manipulative recommendation",
            "hidden persuasion AI",
            "subconscious influence AI",
            "behavioral manipulation AI",
        ),
        code_signals=(
            "subliminal_nudge",
            "dark_pattern",
            "manipulate_behavior",
            "hidden_persuasion",
            "deceptive_ui",
            "covert_influence",
        ),
        exceptions=(),
        applies_from="2025-02-02",
    ),
    ProhibitedEntry(
        article="Art.5(1)(b)",
        title="Exploiting vulnerabilities of persons or groups causing significant harm",
        keywords=(
            "vulnerability exploitation AI",
            "exploit elderly AI",
            "exploit disability AI",
            "exploit poverty AI",
            "socioeconomic vulnerability AI",
            "age-based manipulation AI",
        ),
        code_signals=(
            "exploit_vulnerability",
            "target_vulnerable",
            "elderly_exploit",
            "disability_exploit",
            "vulnerability_target",
        ),
        exceptions=(),
        applies_from="2025-02-02",
    ),
    ProhibitedEntry(
        article="Art.5(1)(c)",
        title="Social scoring of natural persons or groups",
        keywords=(
            "social scoring",
            "social credit score",
            "citizen scoring",
            "social trustworthiness score",
            "social behavior scoring",
            "citizen ranking system",
            "loyalty score",
        ),
        code_signals=(
            "social_score",
            "social_credit",
            "citizen_score",
            "trustworthiness_score",
            "social_ranking",
            "behavior_score_citizen",
        ),
        exceptions=(),
        applies_from="2025-02-02",
    ),
    ProhibitedEntry(
        article="Art.5(1)(d)",
        title="Predictive criminal risk assessment based solely on profiling or traits",
        keywords=(
            "predictive criminal profiling",
            "predictive policing based on character",
            "criminal personality prediction",
            "crime prediction from traits",
            "pre-crime AI",
            "offending prediction from profile alone",
        ),
        code_signals=(
            "predict_crime_from_profile",
            "criminal_personality",
            "pre_crime",
            "crime_prediction_trait",
            "predictive_criminal",
        ),
        exceptions=(
            "systems supporting human assessment based on objective, verifiable facts "
            "directly linked to criminal activity",
        ),
        applies_from="2025-02-02",
    ),
    ProhibitedEntry(
        article="Art.5(1)(e)",
        title="Untargeted facial recognition database creation via scraping",
        keywords=(
            "facial recognition database scraping",
            "untargeted face scraping",
            "bulk face image collection",
            "facial data harvesting",
            "face scraping CCTV",
            "internet face scraping",
        ),
        code_signals=(
            "scrape_faces",
            "face_scrape",
            "bulk_face_collect",
            "face_database_scrape",
            "harvest_faces",
            "untargeted_biometric_scrape",
        ),
        exceptions=(),
        applies_from="2025-02-02",
    ),
    ProhibitedEntry(
        article="Art.5(1)(f)",
        title="Emotion inference in workplace or educational institutions",
        keywords=(
            "workplace emotion AI",
            "employee emotion detection",
            "classroom emotion AI",
            "student emotion monitoring",
            "worker mood detection",
            "emotion inference workplace",
            "emotion inference education",
            "affect recognition at work",
            "office emotion surveillance",
        ),
        code_signals=(
            "workplace_emotion",
            "employee_emotion",
            "classroom_emotion",
            "student_emotion",
            "worker_mood",
            "detect_emotion_employee",
            "emotion_inference_work",
            "affect_recognition_school",
        ),
        exceptions=("medical or safety purposes",),
        applies_from="2025-02-02",
    ),
    ProhibitedEntry(
        article="Art.5(1)(g)",
        title="Biometric-based categorization to deduce sensitive attributes",
        keywords=(
            "race inference from biometrics",
            "political opinion inference biometrics",
            "sexual orientation inference biometrics",
            "religious belief inference biometrics",
            "trade union inference biometrics",
            "sensitive attribute biometric classification",
        ),
        code_signals=(
            "infer_race_biometric",
            "biometric_political",
            "sexual_orientation_biometric",
            "religion_biometric",
            "trade_union_biometric",
            "sensitive_biometric_classify",
        ),
        exceptions=(
            "labeling/filtering of lawfully acquired biometric datasets in law enforcement",
        ),
        applies_from="2025-02-02",
    ),
    ProhibitedEntry(
        article="Art.5(1)(h)",
        title="Real-time remote biometric identification in public spaces by law enforcement",
        keywords=(
            "real-time facial recognition public",
            "live RBI",
            "real-time biometric identification public",
            "live face recognition street",
            "real-time biometric surveillance",
            "CCTV real-time face recognition",
        ),
        code_signals=(
            "realtime_rbi",
            "live_face_recognition",
            "realtime_biometric_id",
            "live_rbi",
            "public_space_biometric",
            "surveillance_realtime_face",
        ),
        exceptions=(
            "targeted search for specific missing persons or trafficking victims",
            "preventing specific substantial imminent threat to life or terrorist attack",
            "identifying suspects of serious criminal offenses carrying 4+ year sentences listed in Annex II",
        ),
        applies_from="2025-02-02",
    ),
    ProhibitedEntry(
        article="Art.5(1)(i)",
        title="Non-consensual sexually explicit imagery or CSAM generation (AI Omnibus)",
        keywords=(
            "nudify AI",
            "nudification AI",
            "non-consensual intimate imagery AI",
            "deepfake nude",
            "CSAM AI",
            "child sexual abuse material AI",
            "synthetic CSAM",
            "non-consensual explicit imagery",
        ),
        code_signals=(
            "nudify",
            "nudification",
            "deepfake_nude",
            "csam_generate",
            "intimate_imagery_generate",
            "explicit_deepfake",
            "synthetic_nude",
        ),
        exceptions=(
            "systems with effective technical safeguards that reliably prevent prohibited outputs",
        ),
        applies_from="2026-12-02",
    ),
]


def match_prohibited(text: str) -> list[ProhibitedEntry]:
    from opencomplai_core.scanner.detectors._signals import match_code_signal

    text_lower = text.lower()
    matched: list[ProhibitedEntry] = []
    for entry in PROHIBITED:
        if any(match_code_signal(text, sig) for sig in entry.code_signals):
            matched.append(entry)
            continue
        if any(kw in text_lower for kw in entry.keywords):
            matched.append(entry)
    return matched
