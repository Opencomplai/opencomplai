from __future__ import annotations

import pytest
from opencomplai_ai.classifier import IntentClassifier


@pytest.mark.parametrize(
    ("token", "ref"),
    [
        ("stable_diffusion", "Art.50(2)"),
        ("face_swap", "Art.50(4), first subparagraph"),
        ("generate_news", "Art.50(4), second subparagraph"),
        ("chatbot", "Art.50(1)"),
    ],
)
def test_classifier_cites_corrected_paragraph(token, ref):
    result = IntentClassifier().classify(token, token=token)
    assert result is not None
    assert result.risk_tier == "limited_risk"
    assert result.regulation_ref == ref
