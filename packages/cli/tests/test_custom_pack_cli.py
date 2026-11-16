"""`--custom-pack` on `gaps` and `check`, end to end.

A custom controls pack is a data file of attestation-led controls. It is assessed
as a further framework, `CUSTOM_<key>`: its rows read Unverified until attested,
and it gates only when its key is listed in `--gate` or `gate.frameworks`.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from opencomplai_cli import main
from opencomplai_core.attestation_bundle import (
    AttestationBundle,
    bundle_sha256,
    bundle_signing_bytes,
)
from opencomplai_core.frameworks import FRAMEWORKS
from rich.console import Console
from typer.testing import CliRunner

KEY = "CUSTOM_ACME"
ROW_1 = f"{KEY}:AC-1"
ROW_2 = f"{KEY}:AC-2"
ARTIFACT = Path("compliance-artifact.json")

PACK_YAML = """\
format: opencomplai/custom-pack/v1
key: ACME
label: Acme internal AI controls
controls:
  - id: AC-1
    title: Model inventory reviewed each quarter
    default_ttl_days: 90
  - id: AC-2
    title: Customer-facing outputs reviewed before launch
"""


@pytest.fixture(autouse=True)
def _custom_packs_are_per_process_state():
    """The registry is global: drop every custom pack a test loaded."""
    yield
    for key in [k for k in FRAMEWORKS if k.startswith("CUSTOM_")]:
        del FRAMEWORKS[key]
    main._CUSTOM_PACKS_LOADED.clear()


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """Run the CLI in a temp repo; returns (exit code, stdout, stderr)."""
    monkeypatch.chdir(tmp_path)
    for var in (
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
        "OPENCOMPLAI_DASHBOARD_URL",
        "SIGNING_KEY_PRIVATE",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    home = tmp_path / "home"
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home)
    monkeypatch.setattr(main, "_CONFIG_FILE", home / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "signing.pub")

    out, err = io.StringIO(), io.StringIO()
    for name, buffer in (("console", out), ("err_console", err)):
        monkeypatch.setattr(
            main, name, Console(file=buffer, width=300, color_system=None)
        )

    def run(*args: str) -> tuple[int, str, str]:
        for buffer in (out, err):
            buffer.seek(0)
            buffer.truncate()
        result = CliRunner().invoke(main.app, list(args))
        return result.exit_code, out.getvalue(), err.getvalue()

    code, _, stderr = run(
        "init",
        "--system-id",
        "custom-sys",
        "--intended-purpose",
        "customer support chatbot for an online shop",
    )
    assert code == 0, stderr
    return run


@pytest.fixture
def pack(tmp_path) -> Path:
    path = tmp_path / "acme.yaml"
    path.write_text(PACK_YAML, encoding="utf-8")
    return path


def _set_manifest(**fields: object) -> None:
    path = Path("system-manifest.json")
    manifest = json.loads(path.read_text())
    manifest.update(fields)
    path.write_text(json.dumps(manifest, indent=2))


def _attested(*row_ids: str) -> dict:
    return {
        KEY: {
            "attested": {
                rid: {
                    "statement": "Reviewed and recorded.",
                    "attested_by": "Jane Doe",
                    "attested_at": "2026-10-12",
                    "valid_until": "2099-01-01",
                }
                for rid in row_ids
            }
        }
    }


def _artifact() -> dict:
    return json.loads(ARTIFACT.read_text())


def _rows(framework_report: dict) -> dict[str, str]:
    return {r["article"]: r["status"] for r in framework_report["report"]["articles"]}


def _bundle(attestations: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "schema_version": "attestation_bundle/v1",
        "system_id": None,
        "issued_at": "2026-11-03T09:30:00+00:00",
        "attestations": attestations,
        "excluded": {},
        "key_id": "test-key",
        "signature": "AAAA",
    }
    digest = bundle_sha256(AttestationBundle.model_validate(raw))
    signature = Ed25519PrivateKey.generate().sign(bundle_signing_bytes(digest))
    return {**raw, "signature": base64.b64encode(signature).decode()}


# --- gaps --------------------------------------------------------------------------


def test_gaps_prints_the_pack_label_and_row_ids(cli, pack):
    code, stdout, stderr = cli("gaps", "--custom-pack", str(pack))

    assert code == 0, stderr
    assert "Acme internal AI controls (custom pack, attestation-led)" in stdout
    assert ROW_1 in stdout
    assert ROW_2 in stdout
    assert "Model inventory reviewed each quarter" in stdout
    assert "UNVERIFIED" in stdout.upper()


def test_gaps_json_has_the_custom_framework_block(cli, pack):
    code, stdout, stderr = cli("gaps", "--custom-pack", str(pack), "-o", "json")

    assert code == 0, stderr
    frameworks = json.loads(stdout)["payload"]["frameworks"]
    assert list(frameworks) == ["EU_AI_ACT", KEY]
    assert frameworks[KEY]["derived_from"] is None
    assert frameworks[KEY]["disclaimer_ref"] == "DISCLAIMER_V2"
    assert set(_rows(frameworks[KEY])) == {ROW_1, ROW_2}
    assert set(_rows(frameworks[KEY]).values()) == {"unverified"}


def test_the_pack_is_not_added_twice_when_it_is_already_a_target(cli, pack):
    code, stdout, _ = cli(
        "gaps", "--custom-pack", str(pack), "--target", KEY, "-o", "json"
    )

    assert code == 0
    assert list(json.loads(stdout)["payload"]["frameworks"]) == [KEY]


def test_an_attested_row_reads_met(cli, pack):
    _set_manifest(framework_inputs=_attested(ROW_1))

    code, stdout, stderr = cli("gaps", "--custom-pack", str(pack), "-o", "json")

    assert code == 0, stderr
    rows = _rows(json.loads(stdout)["payload"]["frameworks"][KEY])
    assert rows == {ROW_1: "met", ROW_2: "unverified"}


def test_a_label_with_markup_is_printed_literally(cli, tmp_path):
    path = tmp_path / "markup.yaml"
    path.write_text(
        PACK_YAML.replace(
            "Acme internal AI controls", "Acme [red]alert[/red] controls"
        ).replace("Model inventory", "Inventory [bold]b[/bold]"),
        encoding="utf-8",
    )

    code, stdout, stderr = cli("gaps", "--custom-pack", str(path))

    assert code == 0, stderr
    assert "Acme [red]alert[/red] controls" in stdout
    assert "Inventory [bold]b[/bold] reviewed each quarter" in stdout


def test_a_bad_file_exits_2_with_a_short_message(cli, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(PACK_YAML.replace("key: ACME", "key: acme"), encoding="utf-8")

    code, stdout, stderr = cli("gaps", "--custom-pack", str(bad))

    assert code == 2
    assert "custom pack:" in stderr
    assert "key" in stderr
    assert stdout == ""
    assert KEY not in FRAMEWORKS


def test_a_missing_file_exits_2(cli, tmp_path):
    code, _, stderr = cli("gaps", "--custom-pack", str(tmp_path / "nope.yaml"))

    assert code == 2
    assert "custom pack:" in stderr


def test_an_error_message_in_markup_is_not_interpreted(cli, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("[red]boom[/red]: [unclosed", encoding="utf-8")

    code, _, stderr = cli("gaps", "--custom-pack", str(bad))

    assert code == 2
    assert "custom pack:" in stderr


# --- check -------------------------------------------------------------------------


def test_check_with_gaps_writes_the_custom_framework_report_and_exits_as_before(
    cli, pack
):
    without, _, _ = cli("check", "--with-gaps")
    assert without == 0
    assert "framework_reports" not in _artifact()

    code, _, stderr = cli("check", "--with-gaps", "--custom-pack", str(pack))

    assert code == without, stderr
    artifact = _artifact()
    assert artifact["result"] == "pass"
    reports = artifact["framework_reports"]
    assert list(reports) == ["EU_AI_ACT", KEY]
    assert (
        reports[KEY]["label"]
        == "Acme internal AI controls (custom pack, attestation-led)"
    )
    assert set(_rows(reports[KEY])) == {ROW_1, ROW_2}
    assert "gated" not in reports[KEY] or reports[KEY]["gated"] is False


def test_the_pack_does_not_gate_unless_its_key_is_listed(cli, pack):
    code, _, stderr = cli(
        "check",
        "--with-gaps",
        "--custom-pack",
        str(pack),
        "--gate-fail-on",
        "unverified",
    )

    assert code == 0, stderr
    assert _artifact()["failed_controls"] == []


def test_a_gated_pack_fails_on_unattested_rows_with_fail_on_unverified(cli, pack):
    Path("opencomplai.yaml").write_text(
        f"gate:\n  frameworks: [{KEY}]\n  fail_on: unverified\n", encoding="utf-8"
    )

    code, _, stderr = cli("check", "--custom-pack", str(pack))

    assert code == 1, stderr
    artifact = _artifact()
    assert artifact["result"] == "control_fail"
    assert artifact["failed_controls"] == [ROW_1, ROW_2]


def test_attested_rows_do_not_fail_the_gate(cli, pack):
    _set_manifest(framework_inputs=_attested(ROW_1, ROW_2))
    Path("opencomplai.yaml").write_text(
        f"gate:\n  frameworks: [{KEY}]\n  fail_on: unverified\n", encoding="utf-8"
    )

    code, _, stderr = cli("check", "--custom-pack", str(pack))

    assert code == 0, stderr
    assert _artifact()["failed_controls"] == []


def test_a_gated_pack_with_the_default_level_never_fails_on_unverified_rows(cli, pack):
    code, _, stderr = cli("check", "--custom-pack", str(pack), "--gate", KEY)

    assert code == 0, stderr
    assert _artifact()["failed_controls"] == []


@pytest.mark.parametrize("level", ["missing", "partial"])
def test_check_warns_when_a_gated_pack_cannot_fail_at_the_level(cli, pack, level):
    code, _, stderr = cli(
        "check", "--custom-pack", str(pack), "--gate", KEY, "--gate-fail-on", level
    )

    assert code == 0, stderr
    warning = next(line for line in stderr.splitlines() if "WARN" in line)
    assert KEY in warning
    assert f"fail_on '{level}'" in warning
    assert "'unverified'" in warning


def test_check_warns_at_the_default_level_from_the_project_file(cli, pack):
    Path("opencomplai.yaml").write_text(
        f"gate:\n  frameworks: [{KEY}]\n", encoding="utf-8"
    )

    code, _, stderr = cli("check", "--custom-pack", str(pack))

    assert code == 0, stderr
    assert f"gated custom pack {KEY} cannot fail the gate at fail_on 'missing'" in (
        stderr
    )


def test_check_does_not_warn_at_unverified_or_when_the_pack_is_not_gated(cli, pack):
    gated, _, gated_err = cli(
        "check",
        "--custom-pack",
        str(pack),
        "--gate",
        KEY,
        "--gate-fail-on",
        "unverified",
    )
    ungated, _, ungated_err = cli("check", "--custom-pack", str(pack))

    assert (gated, ungated) == (1, 0)
    assert "cannot fail the gate" not in gated_err
    assert "cannot fail the gate" not in ungated_err


def test_gaps_warns_when_a_gated_pack_cannot_fail_at_the_level(cli, pack):
    Path("opencomplai.yaml").write_text(
        f"gate:\n  frameworks: [{KEY}]\n", encoding="utf-8"
    )

    code, stdout, stderr = cli("gaps", "--custom-pack", str(pack), "-o", "json")

    assert code == 0, stderr
    assert f"gated custom pack {KEY} cannot fail the gate at fail_on 'missing'" in (
        stderr
    )
    assert json.loads(stdout)["payload"]["frameworks"][KEY]  # stdout stays JSON


def test_gaps_prints_nothing_from_a_fail_on_it_does_not_know(cli, pack):
    # The project file is checked when it is read, so a level it does not know is
    # refused with a short message: here a line break, an escape character and a
    # second line.
    Path("opencomplai.yaml").write_text(
        f'gate:\n  frameworks: [{KEY}]\n  fail_on: "missing\\n\\e[31mFORGED-WARN"\n',
        encoding="utf-8",
    )

    code, _, stderr = cli("gaps", "--custom-pack", str(pack), "-o", "json")

    assert code == 2, stderr
    assert "gate.fail_on must be" in stderr
    assert "FORGED-WARN" not in stderr
    assert "\x1b" not in stderr
    assert "cannot fail the gate" not in stderr


def test_gaps_does_not_warn_at_unverified_or_without_the_pack(cli, pack):
    Path("opencomplai.yaml").write_text(
        f"gate:\n  frameworks: [{KEY}]\n  fail_on: unverified\n", encoding="utf-8"
    )
    code, _, stderr = cli("gaps", "--custom-pack", str(pack))
    assert code == 0, stderr
    assert "cannot fail the gate" not in stderr

    # Gated but not assessed in this run: nothing to warn about.
    Path("opencomplai.yaml").write_text(
        f"gate:\n  frameworks: [{KEY}]\n", encoding="utf-8"
    )
    code, _, stderr = cli("gaps")
    assert code == 0, stderr
    assert "cannot fail the gate" not in stderr


def test_gating_on_a_pack_that_is_not_loaded_exits_2(cli):
    Path("opencomplai.yaml").write_text(
        f"gate:\n  frameworks: [{KEY}]\n", encoding="utf-8"
    )

    code, _, stderr = cli("check")

    assert code == 2
    assert KEY in stderr
    assert "(load it with --custom-pack)" in stderr


def test_check_with_a_bad_pack_exits_2_and_writes_nothing(cli, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")

    code, _, stderr = cli("check", "--with-gaps", "--custom-pack", str(bad))

    assert code == 2
    assert "custom pack:" in stderr
    assert not ARTIFACT.exists()


def test_a_run_over_several_manifests_loads_the_pack_once(cli, pack):
    first = json.loads(Path("system-manifest.json").read_text())
    second = {**first, "system_id": "second-sys"}
    Path("second.json").write_text(json.dumps(second), encoding="utf-8")

    code, _, stderr = cli(
        "check",
        "-m",
        "system-manifest.json",
        "-m",
        "second.json",
        "--with-gaps",
        "--custom-pack",
        str(pack),
        "--output-dir",
        "out",
    )

    assert code == 0, stderr
    for system in ("custom-sys", "second-sys"):
        artifact = json.loads(
            Path("out", system, "compliance-artifact.json").read_text()
        )
        assert KEY in artifact["framework_reports"]


# --- report ---------------------------------------------------------------------------


def test_report_shows_the_custom_section_from_the_artifact(cli, pack):
    assert cli("check", "--with-gaps", "--custom-pack", str(pack))[0] == 0

    code, _, stderr = cli("report", "--artifact", str(ARTIFACT), "-o", "report.html")

    assert code == 0, stderr
    html = Path("report.html").read_text(encoding="utf-8")
    assert "Acme internal AI controls (custom pack, attestation-led)" in html
    assert ROW_1 in html
    assert ROW_2 in html


def test_report_escapes_a_label_and_a_title_with_html(cli, tmp_path):
    hostile = tmp_path / "hostile.yaml"
    hostile.write_text(
        PACK_YAML.replace(
            "label: Acme internal AI controls", "label: <script>x</script>"
        ).replace(
            "title: Model inventory reviewed each quarter", "title: <script>x</script>"
        ),
        encoding="utf-8",
    )
    assert cli("check", "--with-gaps", "--custom-pack", str(hostile))[0] == 0

    # The pack is still loaded in this process, so the title column is filled.
    code, _, stderr = cli("report", "--artifact", str(ARTIFACT), "-o", "report.html")

    assert code == 0, stderr
    html = Path("report.html").read_text(encoding="utf-8")
    assert "<script>x</script>" not in html
    assert html.count("&lt;script&gt;x&lt;/script&gt;") >= 2


def test_report_in_a_later_run_shows_a_dash_for_titles_it_does_not_have(cli, pack):
    assert cli("check", "--with-gaps", "--custom-pack", str(pack))[0] == 0
    del FRAMEWORKS[KEY]  # a separate process would not have the pack

    code, _, stderr = cli("report", "--artifact", str(ARTIFACT), "-o", "report.html")

    assert code == 0, stderr
    html = Path("report.html").read_text(encoding="utf-8")
    assert ROW_1 in html
    assert "Model inventory reviewed each quarter" not in html


# --- attestations carried without the pack -------------------------------------------------


def test_a_manifest_with_custom_attestations_works_without_the_pack(cli):
    _set_manifest(framework_inputs=_attested(ROW_1))

    code, _, stderr = cli("check", "--with-gaps")

    assert code == 0, stderr
    assert "framework_reports" not in _artifact()
    code, stdout, stderr = cli("gaps", "-o", "json")
    assert code == 0, stderr
    assert "frameworks" not in json.loads(stdout)["payload"]


def test_a_bundle_with_custom_entries_is_ignored_without_the_pack(cli, tmp_path):
    record = {
        "statement": "Reviewed.",
        "attested_by": "Jane Doe",
        "attested_at": "2026-10-12",
        "valid_until": "2099-01-01",
        "record_id": "rec_1",
    }
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(_bundle({KEY: {ROW_1: record}})), encoding="utf-8")

    code, _, stderr = cli("check", "--with-gaps", "--attestations-file", str(path))

    assert code == 0, stderr
    assert "unknown framework" in stderr
    assert KEY in stderr

    # With the pack the same bundle decides the row.
    pack_file = tmp_path / "acme.yaml"
    pack_file.write_text(PACK_YAML, encoding="utf-8")
    code, stdout, stderr = cli(
        "gaps",
        "--custom-pack",
        str(pack_file),
        "--attestations-file",
        str(path),
        "-o",
        "json",
    )
    assert code == 0, stderr
    rows = _rows(json.loads(stdout)["payload"]["frameworks"][KEY])
    assert rows == {ROW_1: "met", ROW_2: "unverified"}
