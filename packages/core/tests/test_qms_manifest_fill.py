"""QMS document: manifest fill, micro profile and EN 18286 cross-check (SU-24a2)."""

from __future__ import annotations

import json

import pytest
from opencomplai_core.models import SystemManifest
from opencomplai_core.qms_document import (
    build_qms_document,
    render_qms_document_markdown,
)
from pydantic import ValidationError

_NOW = "2026-01-01T00:00:00+00:00"


def _manifest(**kw: object) -> SystemManifest:
    return SystemManifest(system_id="s", intended_purpose="credit scoring", **kw)


def _clause(doc, letter):
    return next(c for c in doc.clauses if c.letter == letter)


def test_empty_manifest_fields_fill_nothing(tmp_path):
    doc = build_qms_document(
        tmp_path, generated_at=_NOW, manifest=_manifest(monitoring_approach="   ")
    )
    for letter in "ehi":
        assert _clause(doc, letter).manifest_content == ""
        assert _clause(doc, letter).manifest_source == ""
    assert "Manifest-declared" in render_qms_document_markdown(doc)


def test_micro_profile_only_for_micro(tmp_path):
    for size in ("micro", "small", "medium", "large", None):
        kw = {} if size is None else {"organisation_size": size}
        doc = build_qms_document(tmp_path, manifest=_manifest(**kw))
        assert len(doc.profile_notes) == (size == "micro")
        if size == "micro":
            note = doc.profile_notes[0]
            assert note.needs_founder_review
            assert note.confidence == "low"
            assert "Profile notes" in render_qms_document_markdown(doc)
    assert build_qms_document(tmp_path).profile_notes == []


@pytest.mark.parametrize(
    ("declared", "expected"),
    [
        (["EN 18286"], True),
        (["en-18286:2026"], True),
        (["EN18286"], True),
        (["EN 12345"], False),
        ([], False),
    ],
)
def test_en_18286_listed_and_cross_checked(tmp_path, declared, expected):
    doc = build_qms_document(
        tmp_path, manifest=_manifest(harmonised_standards=declared)
    )
    (std,) = doc.standards
    assert std.id == "EN-18286"
    assert std.status == "published"
    assert std.declared_in_manifest is expected
    assert "Catalogue status: `published`" in render_qms_document_markdown(doc)


def test_en_18286_no_manifest_not_checked(tmp_path):
    doc = build_qms_document(tmp_path)
    assert doc.standards[0].declared_in_manifest is None
    assert "Declared in manifest: not checked" in render_qms_document_markdown(doc)


def test_manifest_text_does_not_change_probe_counts(tmp_path):
    plain = build_qms_document(tmp_path)
    filled = build_qms_document(
        tmp_path, manifest=_manifest(incident_response_procedure="runbook")
    )
    assert (plain.present_count, plain.missing_count) == (
        filled.present_count,
        filled.missing_count,
    )
    assert _clause(filled, "i").manifest_content == "runbook"


def test_organisation_size_omitted_when_unset():
    assert "organisation_size" not in json.loads(_manifest().model_dump_json())
    assert (
        json.loads(_manifest(organisation_size="micro").model_dump_json())[
            "organisation_size"
        ]
        == "micro"
    )
    with pytest.raises(ValidationError):
        _manifest(organisation_size="huge")
