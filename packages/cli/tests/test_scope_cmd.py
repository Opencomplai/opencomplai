"""`opencomplai scope`: answers written to the manifest, outcome and scoped-out rows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_core import pack_registry
from opencomplai_core.applicability import load_applicability
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack, pack_requirements
from typer.testing import CliRunner

FW = "ISO_IEC_27090"
FIXTURE_REQUIREMENTS = (
    Path(__file__).resolve().parents[2]
    / "core"
    / "tests"
    / "fixtures"
    / "framework_pack"
    / "requirements.json"
)
APPLICABILITY = {
    "default": "applies",
    "questions": [
        {"key": "sells_in_eu", "text": "Sold in the EU", "false_means": "is not sold"},
        {"key": "handles_cards", "text": "Handles cards", "false_means": "no cards"},
    ],
    "outcomes": [
        {
            "when": {"sells_in_eu": False},
            "outcome": "not_applicable",
            "reason": "The system is not sold in the EU.",
        }
    ],
}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    home = tmp_path / "home"
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home)
    monkeypatch.setattr(main, "_CONFIG_FILE", home / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "signing.pub")
    result = CliRunner().invoke(
        main.app,
        ["init", "--system-id", "scope-sys", "--intended-purpose", "credit scoring"],
    )
    assert result.exit_code == 0, result.output
    return tmp_path


def _run(*args: str):
    return CliRunner().invoke(main.app, ["scope", *args])


def _manifest() -> dict:
    return json.loads(Path("system-manifest.json").read_text(encoding="utf-8"))


def _scoped_out_ids(keys: set[str]) -> set[str]:
    """Rows whose scope_out has a group made only of `keys`."""
    rows = pack_requirements(FRAMEWORKS[FW])
    return {
        rid
        for rid, config in rows.items()
        if any(set(group) <= keys for group in config.get("scope_out", []))
    }


def test_answers_are_written_and_rows_listed(repo):
    result = _run(
        FW,
        "--answer", "trains_models=no",
        "--answer", "uses_retrieval=no",
        "--output", "json",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["framework"] == FW
    pack_default = (load_applicability(FW) or {}).get("default")
    assert data["outcome"] == pack_default
    assert data["reason"] == ""  # the pack default carries no reason
    assert data["scope"] == {"trains_models": False, "uses_retrieval": False}
    assert _manifest()["framework_inputs"][FW]["scope"] == data["scope"]
    expected = _scoped_out_ids({"trains_models", "uses_retrieval"})
    assert expected
    assert set(data["scoped_out"]) == expected
    assert all(data["scoped_out"][rid] for rid in expected)


def test_second_run_changes_only_that_key(repo):
    _run(
        FW,
        "--answer",
        "trains_models=no",
        "--answer",
        "uses_retrieval=no",
        "-o",
        "json",
    )
    before = _manifest()
    result = _run(FW, "--answer", "trains_models=yes", "-o", "json")
    assert result.exit_code == 0, result.output
    after = _manifest()
    scope = after["framework_inputs"][FW]["scope"]
    assert scope == {"trains_models": True, "uses_retrieval": False}
    before["framework_inputs"][FW]["scope"]["trains_models"] = True
    assert after == before
    assert list(after) == list(before)


def test_manifest_keeps_two_space_indent(repo):
    _run(FW, "--answer", "public_api=no", "-o", "json")
    text = Path("system-manifest.json").read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), indent=2) + "\n"


def test_human_output(repo):
    result = _run(FW, "--answer", "trains_models=no")
    assert result.exit_code == 0, result.output
    assert "requirements are out of scope" in result.output
    assert " of " in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["EU_AI_ACT"],
        ["NOPE"],
        [FW, "--answer", "bogus_key=yes"],
        [FW, "--answer", "trains_models=maybe"],
        [FW, "--answer", "trains_models"],
        [FW, "--answer", "trains_models=no", "--answer", "bogus_key=no"],
    ],
)
def test_refusals_exit_2_and_write_nothing(repo, args):
    before = Path("system-manifest.json").read_bytes()
    result = _run(*args, "--output", "json")
    assert result.exit_code == 2, result.output
    assert Path("system-manifest.json").read_bytes() == before


def test_eu_ai_act_points_to_checker(repo, capsys):
    result = _run("EU_AI_ACT")
    assert result.exit_code == 2
    assert "opencomplai checker" in result.output


def test_missing_manifest_exits_2(repo):
    result = _run(FW, "--manifest", "absent.json", "--answer", "trains_models=no")
    assert result.exit_code == 2
    assert not Path("absent.json").exists()


def test_not_applicable_outcome_from_applicability_file(repo, monkeypatch, tmp_path):
    pack = tmp_path / "packs" / "FIXTURE"
    pack.mkdir(parents=True)
    (pack / "applicability.json").write_text(
        json.dumps(APPLICABILITY), encoding="utf-8"
    )
    monkeypatch.setattr(pack_registry, "PACKS_DIR", tmp_path / "packs")
    monkeypatch.setitem(
        FRAMEWORKS,
        "FIXTURE",
        FrameworkPack("FIXTURE", "Fixture", requirements=FIXTURE_REQUIREMENTS),
    )
    result = _run("FIXTURE", "--answer", "sells_in_eu=no", "-o", "json")
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["outcome"] == "not_applicable"
    assert data["reason"] == "The system is not sold in the EU."
    assert data["scope"] == {"sells_in_eu": False}
    assert _manifest()["framework_inputs"]["FIXTURE"]["scope"] == {"sells_in_eu": False}
    assert data["scoped_out"]  # unattested rows leave when not applicable
