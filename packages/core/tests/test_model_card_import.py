"""Hugging Face model-card import: pure, offline, attested-not-verified."""

import json
import socket
from datetime import date
from pathlib import Path

import pytest
from opencomplai_core.model_card_import import ModelCardError, import_model_card
from opencomplai_core.models import ImportedFieldEvidence, SystemManifest
from pydantic import ValidationError

_LEGACY_MANIFEST = json.loads(
    (Path(__file__).parent / "fixtures" / "legacy_manifest.json").read_text(
        encoding="utf-8"
    )
)

_CARD = (Path(__file__).parent / "fixtures" / "hf_model_card_sample.md").read_text(
    encoding="utf-8"
)
_DAY = date(2001, 2, 3)


def _imp(text=_CARD, name="README.md"):
    return import_model_card(text, source_name=name, today=_DAY)


def _card(front: str) -> str:
    return f"---\n{front}\n---\nbody\n"


def test_fixture_card_maps_three_fields():
    imp = _imp()
    assert set(imp.fields) == {
        "training_data_description",
        "model_architecture",
        "performance_metrics",
    }
    assert imp.fields["training_data_description"] == (
        "Datasets declared in the model card: imdb, sst2"
    )
    assert imp.fields["model_architecture"] == (
        "Declared in the model card: base_model=distilbert-base-uncased; "
        "library=transformers; pipeline=text-classification"
    )
    assert imp.fields["performance_metrics"] == {"imdb/accuracy": 0.93, "imdb/f1": 0.92}
    assert imp.warnings == []


def test_imported_fields_are_marked_attested():
    imp = _imp()
    assert set(imp.evidence) == set(imp.fields)
    for ev in imp.evidence.values():
        assert ev.status == "attested"
        assert ev.source == "huggingface_model_card"
    with pytest.raises(ValidationError):
        ImportedFieldEvidence(
            source="x",
            status="verified",
            source_file="f",
            card_sha256="h",
            imported_on="d",
        )


def test_no_front_matter_raises():
    with pytest.raises(ModelCardError):
        _imp("# just a readme\n")
    with pytest.raises(ModelCardError):
        _imp("---\ndatasets: [a]\n")  # never closed


def test_malformed_yaml_raises():
    with pytest.raises(ModelCardError):
        _imp(_card("datasets: [a, b\n  : :"))
    with pytest.raises(ModelCardError):
        _imp(_card("- just\n- a list"))


def test_non_numeric_and_bool_metrics_dropped_with_warning():
    imp = _imp(
        _card(
            "model-index:\n  - results:\n      - metrics:\n"
            "          - {type: ok, value: 1}\n"
            "          - {type: text, value: high}\n"
            "          - {type: flag, value: true}\n"
            "          - {type: nan, value: .nan}\n"
        )
    )
    assert imp.fields["performance_metrics"] == {"ok": 1.0}
    assert len(imp.warnings) == 3


def test_huge_int_metric_dropped_with_warning():
    imp = _imp(
        _card(
            "model-index:\n  - results:\n      - metrics:\n"
            "          - {type: ok, value: 1}\n"
            f"          - {{type: huge, value: {10**400}}}\n"
        )
    )
    assert imp.fields["performance_metrics"] == {"ok": 1.0}
    assert len(imp.warnings) == 1


def test_deeply_nested_yaml_raises_model_card_error():
    with pytest.raises(ModelCardError):
        _imp(_card("datasets: " + "[" * 5000 + "]" * 5000))


def test_metric_key_collision_keeps_first_and_warns():
    imp = _imp(
        _card(
            "model-index:\n"
            "  - results:\n      - {dataset: {type: d}, metrics: [{type: acc, value: 0.1}]}\n"
            "  - results:\n      - {dataset: {type: d}, metrics: [{type: acc, value: 0.9}]}\n"
        )
    )
    assert imp.fields["performance_metrics"] == {"d/acc": 0.1}
    assert len(imp.warnings) == 1


def test_oversized_input_rejected():
    with pytest.raises(ModelCardError):
        _imp("---\n" + "a: b\n" * 70000 + "---\n")


def test_unmapped_keys_ignored():
    imp = _imp(_card("license: mit\ntags: [a]\nlanguage: en\nfoo: {bar: 1}"))
    assert imp.fields == {}
    assert imp.evidence == {}
    assert imp.warnings == []


def test_evidence_stores_basename_only():
    for name in ("C:\\Users\\me\\secret\\README.md", "/home/me/secret/README.md"):
        ev = _imp(name=name).evidence["model_architecture"]
        assert ev.source_file == "README.md"


def test_import_is_offline(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(socket, "socket", boom)
    assert _imp().fields


def test_imported_on_uses_injected_date():
    assert _imp().evidence["model_architecture"].imported_on == "2001-02-03"


def test_manifest_without_imported_evidence_serialises_unchanged():
    legacy_json = json.dumps(_LEGACY_MANIFEST, indent=2)
    manifest = SystemManifest.model_validate_json(legacy_json)
    assert manifest.imported_evidence == {}
    out = manifest.model_dump_json(indent=2)
    assert out == legacy_json
    assert "imported_evidence" not in out


def test_imported_evidence_round_trips_when_set():
    ev = _imp().evidence["model_architecture"]
    manifest = SystemManifest.model_validate(
        {
            **_LEGACY_MANIFEST,
            "imported_evidence": {"model_architecture": ev.model_dump()},
        }
    )
    again = SystemManifest.model_validate_json(manifest.model_dump_json())
    assert again.imported_evidence == {"model_architecture": ev}
