"""Open scope keys and framework-level applicability."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core import pack_registry
from opencomplai_core.applicability import (
    applicability_outcome,
    declared_scope_keys,
    load_applicability,
    load_scope_keys,
)
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    FRAMEWORKS,
    FrameworkPack,
    evaluate_targets,
)
from opencomplai_core.models import (
    Attestation,
    FrameworkInputs,
    FrameworkScope,
    SystemManifest,
)

FIXTURE_REQUIREMENTS = (
    Path(__file__).parent / "fixtures" / "framework_pack" / "requirements.json"
)

APPLICABILITY = {
    "default": "applies",
    "questions": [
        {
            "key": "sells_in_eu",
            "text": "The system is placed on the EU market",
            "false_means": "is not placed on the EU market",
        },
        {
            "key": "handles_cards",
            "text": "The system handles payment cards",
            "false_means": "does not handle payment cards",
        },
    ],
    "outcomes": [
        {
            "when": {"sells_in_eu": False, "handles_cards": False},
            "outcome": "not_applicable",
            "reason": "no EU market and no payment cards.",
        },
        {
            "when": {"handles_cards": False},
            "outcome": "voluntary",
            "reason": "no payment cards.",
        },
    ],
}

ATTESTATION = Attestation(
    statement="The board approved the policy.",
    attested_by="jane@example.com",
    attested_at="2026-09-01",
)


@pytest.fixture
def temp_pack(monkeypatch, tmp_path: Path):
    pack_dir = tmp_path / "FIXTURE"
    pack_dir.mkdir()
    (pack_dir / "applicability.json").write_text(
        json.dumps(APPLICABILITY), encoding="utf-8"
    )
    monkeypatch.setattr(pack_registry, "PACKS_DIR", tmp_path)
    monkeypatch.setitem(
        FRAMEWORKS,
        "FIXTURE",
        FrameworkPack(
            "FIXTURE", "Fixture framework", requirements=FIXTURE_REQUIREMENTS
        ),
    )
    return pack_dir


def _manifest(**scope: bool | None) -> SystemManifest:
    return SystemManifest(
        system_id="sys",
        intended_purpose="credit scoring",
        framework_inputs={"FIXTURE": FrameworkInputs(scope=FrameworkScope(**scope))},
    )


def _run(manifest: SystemManifest, tmp_path: Path):
    return evaluate_targets(
        manifest, ["FIXTURE"], commit_ref="abc", repo_root=tmp_path
    )["FIXTURE"]


def test_shared_keys_carry_the_reason_texts():
    keys = load_scope_keys()
    assert set(keys) == {"trains_models", "uses_retrieval", "public_api"}
    assert keys["public_api"]["false_means"] == "is not reachable through a public API"


def test_declared_keys_are_shared_plus_questions(temp_pack):
    declared = declared_scope_keys("FIXTURE")
    assert {"sells_in_eu", "handles_cards", "trains_models"} <= set(declared)
    assert "sells_in_eu" not in declared_scope_keys("NIST_AI_RMF")


def test_pack_without_file_has_no_outcome():
    # Pick a pack that has no applicability file today, read from the pack directory.
    bare = next(
        d.name
        for d in sorted(pack_registry.PACKS_DIR.iterdir())
        if d.is_dir() and not (d / "applicability.json").exists()
    )
    assert load_applicability(bare) is None
    assert applicability_outcome(bare, {}) is None


def test_outcomes_first_match_then_default(temp_pack):
    both = {"sells_in_eu": False, "handles_cards": False}
    assert applicability_outcome("FIXTURE", both) == (
        "not_applicable",
        "no EU market and no payment cards.",
    )
    assert applicability_outcome("FIXTURE", {"handles_cards": False}) == (
        "voluntary",
        "no payment cards.",
    )
    assert applicability_outcome("FIXTURE", {"handles_cards": True}) == ("applies", "")
    assert applicability_outcome("FIXTURE", {}) == ("applies", "")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(default="maybe"),
        lambda d: d.update(questions=d["questions"][:1]),
        lambda d: d["questions"][0].update(key="public_api"),
        lambda d: d["outcomes"][0]["when"].update(nope=True),
    ],
)
def test_malformed_file_names_the_file(temp_pack, mutate):
    data = json.loads(json.dumps(APPLICABILITY))
    mutate(data)
    (temp_pack / "applicability.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=r"applicability.json"):
        load_applicability("FIXTURE")


def test_each_outcome_is_reached(temp_pack, tmp_path: Path):
    applies = _run(_manifest(handles_cards=True), tmp_path)
    assert applies.applicability == {"outcome": "applies", "reason": ""}
    assert applies.excluded == {}

    voluntary = _run(_manifest(handles_cards=False), tmp_path)
    assert voluntary.applicability["outcome"] == "voluntary"
    assert voluntary.excluded == {}
    assert [r.article for r in voluntary.report.articles] == [
        "FIXTURE:REQ-1",
        "FIXTURE:REQ-2",
        "FIXTURE:REQ-3",
    ]

    none = _run(_manifest(sells_in_eu=False, handles_cards=False), tmp_path)
    assert none.applicability["outcome"] == "not_applicable"
    assert none.report.articles == []
    assert set(none.excluded) == {"FIXTURE:REQ-1", "FIXTURE:REQ-2", "FIXTURE:REQ-3"}
    assert all(
        text == "Not applicable: no EU market and no payment cards."
        for text in none.excluded.values()
    )


def test_attested_rows_stay_when_not_applicable(temp_pack, tmp_path: Path):
    manifest = _manifest(sells_in_eu=False, handles_cards=False)
    manifest.framework_inputs["FIXTURE"].attested["FIXTURE:REQ-2"] = ATTESTATION
    report = _run(manifest, tmp_path)
    assert [r.article for r in report.report.articles] == ["FIXTURE:REQ-2"]
    assert "FIXTURE:REQ-2" not in report.excluded


def test_undeclared_scope_key_raises(temp_pack, tmp_path: Path):
    with pytest.raises(ValueError, match="'nope' is not a scope key"):
        _run(_manifest(nope=True), tmp_path)


def test_scope_extra_must_be_a_bool():
    with pytest.raises(ValueError, match="must be true, false or null"):
        FrameworkScope(sells_in_eu="yes")
    scope = FrameworkScope(sells_in_eu=False, handles_cards=None, public_api=True)
    assert scope.answers() == {"public_api": True, "sells_in_eu": False}
    assert scope.answer("handles_cards") is None
    assert scope.model_dump() == {"public_api": True, "sells_in_eu": False}


def test_eu_only_run_serialises_without_the_new_field(tmp_path: Path):
    manifest = SystemManifest(system_id="sys", intended_purpose="credit scoring")
    reports = evaluate_targets(
        manifest, [EU_AI_ACT], commit_ref="abc", repo_root=tmp_path
    )
    assert "applicability" not in reports[EU_AI_ACT].model_dump()
    assert "applicability" not in reports[EU_AI_ACT].model_dump(mode="json")


def test_eu_ai_act_still_refuses_scope(tmp_path: Path):
    manifest = SystemManifest(
        system_id="sys",
        intended_purpose="credit scoring",
        framework_inputs={
            EU_AI_ACT: FrameworkInputs(scope=FrameworkScope(trains_models=False))
        },
    )
    with pytest.raises(ValueError, match="supports only `attested`"):
        evaluate_targets(manifest, [EU_AI_ACT], commit_ref="abc", repo_root=tmp_path)
