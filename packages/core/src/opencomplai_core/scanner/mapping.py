"""Signal category to Annex III / Art.5 taxonomy mapping."""

from __future__ import annotations

from opencomplai_core.models import SignalCategory
from opencomplai_core.rules import (
    ANNEX_III_CATEGORIES,
    UNACCEPTABLE_RISK_SIGNALS,
    normalize_text,
)

SIGNAL_TO_TAXONOMY: dict[SignalCategory, list[str]] = {
    SignalCategory.AI_SDK: [],
    SignalCategory.ML_FRAMEWORK: [],
    SignalCategory.LLM_ORCHESTRATION: [],
    SignalCategory.INFERENCE_ENDPOINT: [],
    SignalCategory.MODEL_ARTIFACT: [],
    SignalCategory.EMBEDDINGS_VECTOR: ["essential_services"],
    SignalCategory.PROMPT_AGENT: [],
    SignalCategory.BIOMETRIC: ["biometric"],
    SignalCategory.SCORING_PROFILING: [
        "employment",
        "essential_services",
        "law_enforcement",
    ],
    SignalCategory.PII_DATAFLOW: ["essential_services"],
}

# Annex III area id → taxonomy key (matches ANNEX_III_CATEGORIES after pack remap)
_AREA_TO_TAXONOMY: dict[int, str] = {
    1: "biometric",
    2: "critical_infrastructure",
    3: "education",
    4: "employment",
    5: "essential_services",
    6: "law_enforcement",
    7: "migration",
    8: "justice",
}


def signal_category_to_taxonomy(
    category: SignalCategory,
    token_label: str = "",
    *,
    annex_iii_area: int | None = None,
) -> list[str]:
    if (
        category == SignalCategory.SCORING_PROFILING
        and annex_iii_area is not None
        and annex_iii_area in _AREA_TO_TAXONOMY
    ):
        mapped = [_AREA_TO_TAXONOMY[annex_iii_area]]
    else:
        mapped = list(SIGNAL_TO_TAXONOMY.get(category, []))
    label = normalize_text(token_label)
    for tax_key, keywords in ANNEX_III_CATEGORIES.items():
        if any(normalize_text(kw) in label for kw in keywords):
            if tax_key not in mapped:
                mapped.append(tax_key)
    for signal in UNACCEPTABLE_RISK_SIGNALS:
        if normalize_text(signal) in label and "unacceptable" not in mapped:
            mapped.append("unacceptable")
    return sorted(set(mapped))


def derive_declared_categories(declared_purpose: str) -> list[str]:
    """Reuse AnnexIIIClassifierRule substring matching with normalised text."""
    use_case = normalize_text(declared_purpose)
    matched: list[str] = []
    for category, keywords in ANNEX_III_CATEGORIES.items():
        if any(normalize_text(kw) in use_case for kw in keywords):
            matched.append(category)
    for signal in UNACCEPTABLE_RISK_SIGNALS:
        if normalize_text(signal) in use_case and "unacceptable" not in matched:
            matched.append("unacceptable")
    return sorted(matched)
