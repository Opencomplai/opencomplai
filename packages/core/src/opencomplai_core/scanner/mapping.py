"""Signal category to Annex III / Art.5 taxonomy mapping."""

from __future__ import annotations

from opencomplai_core.models import SignalCategory
from opencomplai_core.rules import ANNEX_III_CATEGORIES, UNACCEPTABLE_RISK_SIGNALS

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


def signal_category_to_taxonomy(
    category: SignalCategory, token_label: str = ""
) -> list[str]:
    mapped = list(SIGNAL_TO_TAXONOMY.get(category, []))
    label = token_label.lower()
    for tax_key, keywords in ANNEX_III_CATEGORIES.items():
        if any(kw in label for kw in keywords):
            if tax_key not in mapped:
                mapped.append(tax_key)
    for signal in UNACCEPTABLE_RISK_SIGNALS:
        if signal in label and "unacceptable" not in mapped:
            mapped.append("unacceptable")
    return sorted(set(mapped))


def derive_declared_categories(declared_purpose: str) -> list[str]:
    """Reuse AnnexIIIClassifierRule substring matching."""
    use_case = declared_purpose.lower()
    matched: list[str] = []
    for category, keywords in ANNEX_III_CATEGORIES.items():
        if any(kw in use_case for kw in keywords):
            matched.append(category)
    for signal in UNACCEPTABLE_RISK_SIGNALS:
        if signal in use_case and "unacceptable" not in matched:
            matched.append("unacceptable")
    return sorted(matched)
