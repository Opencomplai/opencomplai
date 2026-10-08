"""Pins the paragraph and actor of every Art. 50 limited-risk entry."""

from __future__ import annotations

from opencomplai_core.knowledge.limited_risk import LIMITED_RISK

PINNED = {
    "chatbot_interaction": ("Art.50(1)", "provider"),
    "synthetic_content_marking": ("Art.50(2)", "provider"),
    "synthetic_media_deepfake": ("Art.50(4), first subparagraph", "deployer"),
    "emotion_recognition_categorization_disclosure": ("Art.50(3)", "deployer"),
    "ai_generated_text_public_interest": ("Art.50(4), second subparagraph", "deployer"),
}


def _by_type():
    return {e.trigger_type: e for e in LIMITED_RISK}


def test_every_entry_pins_article_and_actor():
    by_type = _by_type()
    assert set(by_type) == set(PINNED)
    assert len(by_type) == len(LIMITED_RISK)
    for trigger, (article, actor) in PINNED.items():
        assert (by_type[trigger].article, by_type[trigger].actor) == (article, actor)


def test_every_entry_is_flagged_for_founder_review():
    for e in LIMITED_RISK:
        assert e.source
        assert e.confidence in {"low", "medium"}
        assert e.needs_founder_review is True


def test_marking_is_provider_and_deepfake_disclosure_is_deployer():
    by_type = _by_type()
    marking = by_type["synthetic_content_marking"]
    assert marking.article == "Art.50(2)"
    assert marking.actor == "provider"
    assert "deployer" not in marking.obligation.lower()
    deepfake = by_type["synthetic_media_deepfake"]
    assert deepfake.article.startswith("Art.50(4)")
    assert deepfake.actor == "deployer"


def test_no_keyword_or_signal_in_two_entries():
    seen: dict[str, str] = {}
    for e in LIMITED_RISK:
        for key in {t.lower() for t in (*e.keywords, *e.code_signals)}:
            assert key not in seen, f"{key!r} in {seen[key]} and {e.trigger_type}"
            seen[key] = e.trigger_type
