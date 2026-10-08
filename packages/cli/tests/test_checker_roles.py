"""Repeatable --entity-type, merged roles and manifest append for `checker`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli.commands import checker as checker_mod
from opencomplai_cli.main import app
from opencomplai_core.control_identity import fingerprint_manifest
from typer.testing import CliRunner

runner = CliRunner()
FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "core"
    / "tests"
    / "fixtures"
    / "checker_golden"
)


@pytest.fixture
def answers_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    fixture = json.loads(
        (FIXTURES / "06_high_risk_provider.json").read_text(encoding="utf-8")
    )
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(fixture["session"]), encoding="utf-8")
    return path


def _run(answers: Path, manifest: Path, *extra: str, **kw):
    return runner.invoke(
        app,
        [
            "checker",
            "--answers",
            str(answers),
            "--write-manifest",
            str(manifest),
            *extra,
        ],
        **kw,
    )


def _create(answers: Path, manifest: Path, *roles: str) -> dict:
    args = ["--intended-purpose", "Screens job applicants"]
    for role in roles:
        args += ["--entity-type", role]
    result = _run(answers, manifest, *args, input="sys-1\n")
    assert result.exit_code == 0, result.output
    return json.loads(manifest.read_text(encoding="utf-8"))


def test_repeated_entity_type_writes_roles_and_obligation_ids(
    answers_path: Path, tmp_path: Path
) -> None:
    data = _create(answers_path, tmp_path / "m.json", "provider", "deployer")
    assert data["operator_role"] == "provider"
    assert data["operator_roles"] == ["provider", "deployer"]
    ids = data["checker_session"]["obligation_ids"]
    assert "provider_high_risk" in ids
    assert "deployer_general" in ids
    assert len(data["checker_session"]["rationale"]) == 2


def test_unknown_entity_type_exits_2(answers_path: Path) -> None:
    result = runner.invoke(
        app, ["checker", "--answers", str(answers_path), "--entity-type", "wizard"]
    )
    assert result.exit_code == 2
    assert "provider" in result.output
    assert "Traceback" not in result.output


def test_write_manifest_appends_and_preserves_other_fields(
    answers_path: Path, tmp_path: Path
) -> None:
    manifest = tmp_path / "m.json"
    data = _create(answers_path, manifest, "provider")
    data["custom_note"] = {"keep": "me"}
    manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")
    keys_before = list(data)

    result = _run(answers_path, manifest, "--entity-type", "deployer")  # no input
    assert result.exit_code == 0, result.output
    after = json.loads(manifest.read_text(encoding="utf-8"))
    assert list(after) == keys_before
    assert after["system_id"] == "sys-1"
    assert after["intended_purpose"] == "Screens job applicants"
    assert after["custom_note"] == {"keep": "me"}
    assert after["operator_role"] == "provider"
    assert after["operator_roles"] == ["provider", "deployer"]
    assert "deployer_general" in after["checker_session"]["obligation_ids"]
    assert "provider_high_risk" in after["checker_session"]["obligation_ids"]


def test_append_is_idempotent_for_same_role(answers_path: Path, tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    first = _create(answers_path, manifest, "provider")
    assert _run(answers_path, manifest, "--entity-type", "provider").exit_code == 0
    second = json.loads(manifest.read_text(encoding="utf-8"))
    assert second["operator_roles"] == ["provider"]
    assert (
        second["checker_session"]["obligation_ids"]
        == first["checker_session"]["obligation_ids"]
    )
    assert (
        second["checker_session"]["rationale"] == first["checker_session"]["rationale"]
    )


def test_verdict_keeps_the_more_severe(answers_path: Path, tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    data = _create(answers_path, manifest, "provider")
    assert data["checker_session"]["verdict"] == "high_risk_ai_system"
    benign = json.loads(
        (FIXTURES / "03_out_of_scope_s1.json").read_text(encoding="utf-8")
    )
    other = tmp_path / "other.json"
    other.write_text(json.dumps(benign["session"]), encoding="utf-8")
    assert _run(other, manifest, "--entity-type", "deployer").exit_code == 0
    after = json.loads(manifest.read_text(encoding="utf-8"))
    assert after["checker_session"]["verdict"] == "high_risk_ai_system"
    assert after["high_risk_presumption"] is True


def test_corrupt_existing_manifest_exits_2_and_is_untouched(
    answers_path: Path, tmp_path: Path
) -> None:
    for content in ("{not json", "[1, 2]"):
        manifest = tmp_path / "bad.json"
        manifest.write_text(content, encoding="utf-8")
        result = _run(answers_path, manifest, "--entity-type", "provider")
        assert result.exit_code == 2
        assert "bad.json" in result.output
        assert manifest.read_text(encoding="utf-8") == content


def test_rationale_in_markdown_and_json_export(
    answers_path: Path, tmp_path: Path
) -> None:
    md, js = tmp_path / "r.md", tmp_path / "r.json"
    result = runner.invoke(
        app,
        [
            "checker",
            "--answers",
            str(answers_path),
            "--entity-type",
            "provider",
            "--entity-type",
            "deployer",
            "--export-md",
            str(md),
            "--export-json",
            str(js),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "## Role rationale" in md.read_text(encoding="utf-8")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert len(data["rationale"]) == 2
    assert "deployer_general" in [o["id"] for o in data["obligations"]]


def test_single_role_run_without_entity_type_keeps_old_manifest_keys(
    answers_path: Path, tmp_path: Path
) -> None:
    manifest = tmp_path / "m.json"
    result = _run(
        answers_path, manifest, "--intended-purpose", "Screens", input="sys-1\n"
    )
    assert result.exit_code == 0, result.output
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert list(data) == [
        "system_id",
        "intended_purpose",
        "compliance_target",
        "high_risk_presumption",
        "commit_ref",
        "operator_role",
        "checker_session",
    ]
    assert "operator_roles" not in data
    assert "rationale" not in data["checker_session"]


def test_fingerprint_unchanged_by_appending_nothing_new(
    answers_path: Path, tmp_path: Path
) -> None:
    manifest = tmp_path / "m.json"
    data = _create(answers_path, manifest)
    assert "operator_roles" not in data
    before = fingerprint_manifest(data)
    assert _run(answers_path, manifest).exit_code == 0
    after = json.loads(manifest.read_text(encoding="utf-8"))
    assert "operator_roles" not in after
    assert fingerprint_manifest(after) == before


def test_wizard_skips_e1_with_preset_entity(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []

    def fake_select(label: str, choices: list) -> str:
        asked.append(label)
        return "eu"

    monkeypatch.setattr(checker_mod, "_confirm", lambda label, default=False: default)
    monkeypatch.setattr(checker_mod, "_select", fake_select)
    session = checker_mod.run_interactive_wizard(
        skip_allowed=False, preset_entity="deployer"
    )
    assert session is not None
    assert session.answers["e1_entity_type"] == "deployer"
    assert not any("kind of entity" in label for label in asked)
