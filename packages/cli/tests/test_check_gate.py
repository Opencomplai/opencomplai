"""`check` gating on frameworks other than the EU AI Act.

Opt-in through opencomplai.yaml `gate: {frameworks, fail_on}` or `--gate` /
`--gate-fail-on`. A gated row fails when it is Missing (or Missing/Partial
with fail_on partial) after exclusions; its id follows the EU ids in
failed_controls and only a PASS turns into CONTROL_FAIL. A bad gate exits 2
before anything is written. Without a gate the output is unchanged (pinned
in test_golden_eu_output.py). The test-only FIXTURE pack proves the generic
path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from opencomplai_core.models import ScanStatusArtifact, SystemState
from opencomplai_core.signing import generate_keypair, verify_artifact
from opencomplai_core.system_state_store import load_state
from typer.testing import CliRunner

FIXTURE_PACK = FrameworkPack(
    "FIXTURE",
    "Fixture framework",
    requirements=Path(__file__).resolve().parents[2]
    / "core"
    / "tests"
    / "fixtures"
    / "framework_pack"
    / "requirements.json",
)

# REQ-2 attested (Met) and REQ-3 excluded, so only REQ-1 can fail.
FIXTURE_INPUTS = {
    "FIXTURE": {
        "excluded": {"FIXTURE:REQ-3": "No deployers: internal tool only."},
        "attested": {
            "FIXTURE:REQ-2": {
                "statement": "The board approved the AI policy.",
                "attested_by": "jane@example.com",
                "attested_at": "2026-09-01",
            }
        },
    }
}

ARTIFACT = Path("compliance-artifact.json")


@pytest.fixture
def check(tmp_path, monkeypatch):
    """A temp repo with a passing chatbot manifest targeting EU_AI_ACT and
    FIXTURE; returns a runner giving (exit code, output)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
    for var in (
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
        "SIGNING_KEY_PRIVATE",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    home = tmp_path / "home"
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home)
    monkeypatch.setattr(main, "_CONFIG_FILE", home / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "signing.pub")

    def run(*args: str) -> tuple[int, str]:
        result = CliRunner().invoke(main.app, list(args))
        return result.exit_code, result.output

    code, output = run(
        "init",
        "--system-id",
        "gate-sys",
        "--intended-purpose",
        "customer support chatbot for an online shop",
    )
    assert code == 0, output
    _set_manifest(
        compliance_targets=["EU_AI_ACT", "FIXTURE"], framework_inputs=FIXTURE_INPUTS
    )
    return run


def _set_manifest(**fields: object) -> None:
    path = Path("system-manifest.json")
    manifest = json.loads(path.read_text())
    manifest.update(fields)
    path.write_text(json.dumps(manifest, indent=2))


def _config(text: str) -> None:
    Path("opencomplai.yaml").write_text(text, encoding="utf-8")


def _risk_register() -> None:
    Path("docs").mkdir(exist_ok=True)
    Path("docs/risk_register.md").write_text(
        "# Risk register\n\nIdentified risks: biased scoring.\n", encoding="utf-8"
    )


def _artifact() -> dict:
    return json.loads(ARTIFACT.read_text())


def _flat(text: str) -> str:
    """Undo Rich's line wrapping."""
    return " ".join(text.split())


def test_ungated_run_passes(check):
    code, output = check("check")
    assert code == 0, output
    assert _artifact()["result"] == "pass"


def test_missing_row_of_gated_framework_fails_the_check(check):
    _config("gate:\n  frameworks: [FIXTURE]\n")

    code, output = check("check")

    assert code == 1, output
    artifact = _artifact()
    assert artifact["result"] == "control_fail"
    # REQ-2 is attested and REQ-3 excluded: neither fails.
    assert artifact["failed_controls"] == ["FIXTURE:REQ-1"]
    # The gate alone attaches no reports; --with-gaps does.
    assert artifact["gap_report"] is None
    assert "framework_reports" not in artifact


def test_unverified_rows_never_fail_and_exclusions_count(check):
    _set_manifest(framework_inputs={})

    code, _ = check("check", "--gate", "FIXTURE")

    assert code == 1
    # REQ-2 without an attestation is Unverified and does not fail.
    assert _artifact()["failed_controls"] == ["FIXTURE:REQ-1", "FIXTURE:REQ-3"]


def test_partial_row_fails_only_with_fail_on_partial(check):
    _risk_register()
    _config("gate:\n  frameworks: [FIXTURE]\n")

    code, output = check("check")
    assert code == 0, output
    assert _artifact()["failed_controls"] == []

    code, _ = check("check", "--gate-fail-on", "partial")
    assert code == 1
    assert _artifact()["failed_controls"] == ["FIXTURE:REQ-1"]

    _config("gate:\n  frameworks: [FIXTURE]\n  fail_on: partial\n")
    code, _ = check("check")
    assert code == 1
    assert _artifact()["failed_controls"] == ["FIXTURE:REQ-1"]


def test_gate_flag_replaces_the_config_list(check):
    # NIST_AI_RMF is not a target, so this config alone would exit 2.
    _config("gate:\n  frameworks: [NIST_AI_RMF]\n")

    code, output = check("check", "--with-gaps", "--gate", "FIXTURE")

    assert code == 1, output
    reports = _artifact()["framework_reports"]
    assert reports["FIXTURE"]["gated"] is True
    assert reports["EU_AI_ACT"]["gated"] is False


def test_nist_gate_fails_on_prefixed_missing_subcategories(check):
    code, output = check(
        "check",
        "--with-gaps",
        "--target",
        "EU_AI_ACT",
        "--target",
        "NIST_AI_RMF",
        "--gate",
        "NIST_AI_RMF",
    )

    assert code == 1, output
    artifact = _artifact()
    nist = artifact["framework_reports"]["NIST_AI_RMF"]
    missing = [
        row["article"]
        for row in nist["report"]["articles"]
        if row["status"] == "missing"
    ]
    assert missing
    assert all(rid.startswith("NIST_AI_RMF:") for rid in missing)
    assert artifact["failed_controls"] == missing
    assert nist["gated"] is True


def test_trap_with_gate_stays_trap_detected_and_halts(check, tmp_path):
    code, output = check(
        "check", "--change-context", "model_retrain", "--gate", "FIXTURE"
    )

    assert code == 4, output
    artifact = _artifact()
    assert artifact["result"] == "trap_detected"
    assert artifact["failed_controls"][0] == "EU_AIA_ART25_MODIFICATION_TRAP"
    assert artifact["failed_controls"][-1] == "FIXTURE:REQ-1"
    assert load_state(tmp_path / "state", "gate-sys") == (
        SystemState.HALTED_PENDING_REVIEW
    )


@pytest.mark.parametrize(
    ("config", "args", "message"),
    [
        ("gate:\n  frameworks: [EU_AI_ACT]\n", (), "EU_AI_ACT cannot be gated"),
        ("", ("--gate", "EU_AI_ACT"), "EU_AI_ACT cannot be gated"),
        ("", ("--gate", "ISO_42001"), "unknown gated framework ISO_42001"),
        ("", ("--gate", "NIST_AI_RMF"), "not among the compliance targets"),
        ("", ("--gate", "FIXTURE", "--gate-fail-on", "unverified"), "fail_on"),
        ("gate:\n  frameworks: [FIXTURE]\n  fail_on: always\n", (), "fail_on"),
        ("gate: [FIXTURE]\n", (), "opencomplai.yaml: gate must be a mapping"),
        ("gate:\n  frameworks: FIXTURE\n", (), "gate.frameworks must be a list"),
        ("scan: [\n", (), "opencomplai.yaml: not valid YAML"),
    ],
)
def test_bad_gate_exits_2_before_writing_anything(check, config, args, message):
    if config:
        _config(config)

    code, output = check("check", "--with-gaps", *args)

    assert code == 2
    assert message in _flat(output)
    assert not ARTIFACT.exists()


def test_signed_gated_artifact_verifies(check, tmp_path, monkeypatch):
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setattr(main, "_SIGNING_KEY", key_dir / "signing.key")

    code, output = check("check", "--sign", "--with-gaps", "--gate", "FIXTURE")

    assert code == 1, output
    artifact = ScanStatusArtifact.model_validate_json(ARTIFACT.read_text())
    assert artifact.failed_controls == ["FIXTURE:REQ-1"]
    assert artifact.framework_reports["FIXTURE"].gated is True
    assert verify_artifact(artifact, key_dir / "signing.pub") is True


def test_gaps_footer_changes_only_for_gated_frameworks(check):
    code, ungated = check("gaps")
    assert code == 0
    assert "gated in CI" not in _flat(ungated)

    _config("gate:\n  frameworks: [FIXTURE]\n  fail_on: partial\n")
    code, gated = check("gaps")
    assert code == 0
    assert (
        "This framework is gated in CI: `opencomplai check` fails on its Missing or "
        "Partial rows (opencomplai.yaml gate)." in _flat(gated)
    )
    # The EU AI Act footer is untouched.
    assert "Gap report is informational only" in _flat(gated)


def test_gaps_nist_footer_says_when_nist_is_gated(check):
    _set_manifest(compliance_targets=["NIST_AI_RMF"], framework_inputs={})

    code, ungated = check("gaps")
    assert code == 0
    assert "NIST AI RMF report is informational only" in _flat(ungated)

    _config("gate:\n  frameworks: [NIST_AI_RMF]\n")
    code, gated = check("gaps")
    assert code == 0
    assert (
        "NIST AI RMF report is gated in CI: `opencomplai check` fails on its "
        "Missing rows (opencomplai.yaml gate)." in _flat(gated)
    )
