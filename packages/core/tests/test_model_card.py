from __future__ import annotations

from datetime import date

from opencomplai_core.model_card import (
    CLOSING_LINE,
    NOT_CAPTURED,
    build_model_card,
    render_model_card_markdown,
)
from opencomplai_core.model_card_import import import_model_card
from opencomplai_core.models import SystemManifest

TODAY = date(2026, 1, 2)
KEYS = [
    "intended_use",
    "model_details",
    "training_data",
    "evaluation",
    "limitations",
    "foreseeable_misuse",
    "human_oversight",
    "monitoring",
    "provenance",
]


def _manifest(**kw: object) -> SystemManifest:
    data: dict[str, object] = {"system_id": "demo", "intended_purpose": "Triage"}
    data.update(kw)
    return SystemManifest.model_validate(data)


def test_nine_sections_in_order() -> None:
    card = build_model_card(_manifest(), today=TODAY)
    assert [s.key for s in card.sections] == KEYS
    text = render_model_card_markdown(card)
    positions = [text.index(f"## {s.title}") for s in card.sections]
    assert positions == sorted(positions)
    assert text.rstrip("\n").endswith(CLOSING_LINE)


def test_empty_fields_say_not_captured() -> None:
    card = build_model_card(_manifest(), today=TODAY)
    by_key = {s.key: s for s in card.sections}
    assert by_key["intended_use"].populated
    for key in KEYS[1:]:
        assert by_key[key].body == NOT_CAPTURED
        assert not by_key[key].populated


def test_metrics_round_trip_through_importer() -> None:
    metrics = {"imdb/accuracy": 0.91, "imdb/f1": 0.88, "squad/em": 0.5, "loss": 1.5}
    card = build_model_card(_manifest(performance_metrics=metrics), today=TODAY)
    text = render_model_card_markdown(card)
    result = import_model_card(text, source_name="MODEL_CARD.md", today=TODAY)
    assert result.fields["performance_metrics"] == metrics


def test_dashes_line_cannot_close_front_matter() -> None:
    metrics = {"d/acc": 0.7}
    card = build_model_card(
        _manifest(intended_purpose="First\n---\nSecond", performance_metrics=metrics),
        today=TODAY,
    )
    text = render_model_card_markdown(card)
    assert text.count("\n---\n") == 1
    assert "\\---" in text
    result = import_model_card(text, source_name="m.md", today=TODAY)
    assert result.fields["performance_metrics"] == metrics


def test_control_characters_are_stripped() -> None:
    card = build_model_card(_manifest(intended_purpose="a\x00b\x1b[31mc"), today=TODAY)
    body = card.sections[0].body
    assert "\x00" not in body
    assert "\x1b" not in body


def test_provenance_lists_imported_evidence() -> None:
    evidence = {
        "performance_metrics": {
            "source": "huggingface_model_card",
            "status": "attested",
            "source_file": "card.md",
            "card_sha256": "ab",
            "imported_on": "2026-01-01",
        }
    }
    card = build_model_card(_manifest(imported_evidence=evidence), today=TODAY)
    prov = card.sections[-1]
    assert prov.populated
    assert "huggingface_model_card" in prov.body
    assert "attested" in prov.body
    assert "2026-01-01" in prov.body
    assert "provider-declared, not verified" in prov.body


def test_same_input_same_bytes() -> None:
    m = _manifest(performance_metrics={"a/b": 1.0, "c/d": 2.0}, known_limitations=["x"])
    a = render_model_card_markdown(build_model_card(m, today=TODAY))
    b = render_model_card_markdown(build_model_card(m, today=TODAY))
    assert a == b
