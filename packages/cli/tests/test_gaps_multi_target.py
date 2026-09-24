"""`gaps`, `check --with-gaps`, `recommend` and `report` across frameworks.

Targets come from repeatable `--target` flags, else the manifest's
`compliance_targets`, else its `compliance_target`. Exactly one EU AI Act or
NIST AI RMF target keeps today's output (pinned in test_golden_eu_output.py);
any other set adds a `frameworks` block to the gaps JSON and prints one block
per target. `recommend` adds fixes for natively evaluated frameworks and
`report` a section per framework from a gaps JSON file. The test-only FIXTURE
pack proves the generic path.
"""

from __future__ import annotations

import html
import io
import json
import re
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from opencomplai_core.models import DISCLAIMER_V1, DISCLAIMER_V2
from rich.console import Console
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

RISK_REGISTER = (
    "# Risk register\n\nIdentified risks: biased scoring.\n"
    "Mitigation: quarterly fairness review; residual risk accepted.\n"
)

# Brackets would be Rich markup if printed unescaped.
STATEMENT = "The board approved the [bold]AI policy[/] on 2026-09-01."

FIXTURE_INPUTS = {
    "FIXTURE": {
        "excluded": {"FIXTURE:REQ-3": "No deployers: internal tool only."},
        "attested": {
            "FIXTURE:REQ-2": {
                "statement": STATEMENT,
                "attested_by": "jane@example.com",
                "attested_at": "2026-09-01",
            }
        },
    }
}


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """Run the CLI in a temp repo; returns (exit code, stdout, stderr)."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "risk_register.md").write_text(RISK_REGISTER, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for var in (
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
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

    code, _, _ = run(
        "init",
        "--system-id",
        "multi-sys",
        "--intended-purpose",
        "credit scoring for loan applications",
    )
    assert code == 0
    return run


@pytest.fixture
def fixture_pack(monkeypatch):
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)


def _set_manifest(**fields: object) -> None:
    path = Path("system-manifest.json")
    manifest = json.loads(path.read_text())
    manifest.update(fields)
    path.write_text(json.dumps(manifest, indent=2))


def _gaps_json(cli, *args: str) -> dict:
    code, stdout, stderr = cli("gaps", *args, "--output", "json")
    assert code == 0, stderr
    return json.loads(stdout)


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_eu_and_nist_json_adds_frameworks_and_neutral_disclaimer(cli):
    envelope = _gaps_json(cli, "--target", "EU_AI_ACT", "--target", "NIST_AI_RMF")
    payload = envelope["payload"]

    assert envelope["disclaimer"] == DISCLAIMER_V2
    # Legacy keys stay: the EU report at the top level and nist_rmf_report.
    assert payload["articles"][0]["article"] == "Art. 4"
    assert len(payload["nist_rmf_report"]["subcategories"]) == 72

    frameworks = payload["frameworks"]
    assert list(frameworks) == ["EU_AI_ACT", "NIST_AI_RMF"]
    eu = frameworks["EU_AI_ACT"]
    assert eu["derived_from"] is None
    assert eu["disclaimer_ref"] == "DISCLAIMER_V1"
    assert eu["report"]["articles"] == payload["articles"]
    assert eu["report"]["principle_summary"] == payload["principle_summary"]

    nist = frameworks["NIST_AI_RMF"]
    assert nist["derived_from"] == "EU_AI_ACT"
    assert nist["disclaimer_ref"] == "DISCLAIMER_V2"
    assert re.fullmatch(r"[0-9a-f]{12}", nist["data_version"])
    rows = {row["article"]: row for row in nist["report"]["articles"]}
    assert len(rows) == 72
    assert rows["NIST_AI_RMF:GOVERN 1.1"]["source"] == "crosswalk"
    assert "Art. 17" in rows["NIST_AI_RMF:GOVERN 1.1"]["evidence_ref"]


def test_eu_and_nist_human_prints_one_block_per_target_in_order(cli):
    code, stdout, stderr = cli(
        "gaps", "--target", "NIST_AI_RMF", "--target", "EU_AI_ACT"
    )
    assert code == 0, stderr

    nist_at = stdout.index("NIST AI RMF 1.0 (derived from EU AI Act evidence)")
    eu_at = stdout.index("Opencomplai Gap Report")
    assert nist_at < eu_at
    assert "NIST_AI_RMF:GOVERN 1.1" in stdout[nist_at:eu_at]
    assert "Principle Summary" in stdout[eu_at:]
    assert DISCLAIMER_V2 in _one_line(stdout[nist_at:eu_at])


def test_manifest_compliance_targets_are_used_without_flags(cli):
    _set_manifest(compliance_targets=["EU_AI_ACT", "NIST_AI_RMF"])
    envelope = _gaps_json(cli)
    assert list(envelope["payload"]["frameworks"]) == ["EU_AI_ACT", "NIST_AI_RMF"]


def test_target_flag_replaces_manifest_targets(cli):
    _set_manifest(compliance_targets=["EU_AI_ACT", "NIST_AI_RMF"])
    envelope = _gaps_json(cli, "--target", "EU_AI_ACT")

    assert envelope["disclaimer"] == DISCLAIMER_V1
    assert "frameworks" not in envelope["payload"]
    assert "nist_rmf_report" not in envelope["payload"]


def test_manifest_compliance_target_nist_prints_nist_table(cli):
    """gaps used to print the EU table whatever the manifest's target was."""
    _set_manifest(compliance_target="NIST_AI_RMF")
    code, stdout, stderr = cli("gaps")
    assert code == 0, stderr
    assert "Opencomplai NIST AI RMF Gap Report" in stdout
    assert "Opencomplai Gap Report" not in stdout


def test_fixture_pack_json_carries_exclusions_and_attestation(cli, fixture_pack):
    _set_manifest(
        compliance_targets=["EU_AI_ACT", "FIXTURE"], framework_inputs=FIXTURE_INPUTS
    )
    envelope = _gaps_json(cli)
    payload = envelope["payload"]

    assert envelope["disclaimer"] == DISCLAIMER_V2
    assert "nist_rmf_report" not in payload
    fixture = payload["frameworks"]["FIXTURE"]
    assert fixture["label"] == "Fixture framework"
    assert fixture["excluded"] == {"FIXTURE:REQ-3": "No deployers: internal tool only."}
    rows = {row["article"]: row for row in fixture["report"]["articles"]}
    assert list(rows) == ["FIXTURE:REQ-1", "FIXTURE:REQ-2"]
    assert rows["FIXTURE:REQ-1"]["evidence_ref"] == "docs/risk_register.md"
    assert rows["FIXTURE:REQ-2"]["status"] == "met"
    assert rows["FIXTURE:REQ-2"]["confidence_label"] == "attested"


def test_fixture_pack_human_prints_generic_table(cli, fixture_pack):
    _set_manifest(
        compliance_targets=["EU_AI_ACT", "FIXTURE"], framework_inputs=FIXTURE_INPUTS
    )
    code, stdout, stderr = cli("gaps")
    assert code == 0, stderr

    eu_at = stdout.index("Opencomplai Gap Report — multi-sys")
    fixture_at = stdout.index("Fixture framework — multi-sys")
    assert eu_at < fixture_at
    block = stdout[fixture_at:]
    for column in ("Requirement", "Title", "Status", "Source", "Evidence"):
        assert column in block
    assert "Risk register maintained" in block
    assert "attestation" in block
    assert STATEMENT in block
    excluded_at = block.index("Excluded")
    assert block.index("FIXTURE:REQ-2") < excluded_at
    assert "FIXTURE:REQ-3: No deployers: internal tool only." in block[excluded_at:]
    assert DISCLAIMER_V2 in _one_line(block[excluded_at:])


def test_unknown_target_exits_2(cli):
    code, stdout, stderr = cli("gaps", "--target", "EU_AI_ACT", "--target", "ISO_42001")
    assert code == 2
    assert stdout == ""
    assert "ISO_42001" in stderr


def test_unknown_manifest_target_exits_2(cli):
    _set_manifest(compliance_targets=["EU_AI_ACT", "ISO_42001"])
    code, _, stderr = cli("gaps")
    assert code == 2
    assert "ISO_42001" in stderr


def test_bad_framework_inputs_exit_2(cli, fixture_pack):
    _set_manifest(
        compliance_targets=["EU_AI_ACT", "FIXTURE"],
        framework_inputs={"FIXTURE": {"excluded": {"FIXTURE:NOPE": "n/a"}}},
    )
    code, stdout, stderr = cli("gaps")
    assert code == 2
    assert stdout == ""
    assert "FIXTURE:NOPE" in stderr


def test_recommend_rejects_eu_framework_inputs(cli):
    _set_manifest(
        framework_inputs={"EU_AI_ACT": {"excluded": {"Art. 9": "not relevant"}}}
    )
    code, _, stderr = cli("recommend")
    assert code == 2
    assert "framework_inputs.EU_AI_ACT" in stderr
    assert not Path("fixes").exists()


def test_check_with_gaps_target_flags_attach_nist_report(cli):
    code, _, stderr = cli(
        "check", "--with-gaps", "--target", "EU_AI_ACT", "--target", "NIST_AI_RMF"
    )
    assert code == 1, stderr  # the credit-scoring EU controls fail, as today
    artifact = json.loads(Path("compliance-artifact.json").read_text())
    assert artifact["gap_report"]["articles"][0]["article"] == "Art. 4"
    assert len(artifact["nist_rmf_report"]["subcategories"]) == 72
    reports = artifact["framework_reports"]
    assert list(reports) == ["EU_AI_ACT", "NIST_AI_RMF"]
    assert reports["EU_AI_ACT"]["report"] == artifact["gap_report"]
    nist = reports["NIST_AI_RMF"]
    assert nist["derived_from"] == "EU_AI_ACT"
    assert nist["gated"] is False
    assert len(nist["report"]["articles"]) == 72
    assert nist["report"]["articles"][0]["article"].startswith("NIST_AI_RMF:")


def test_check_with_gaps_embeds_framework_reports_that_report_renders(
    cli, fixture_pack
):
    _set_manifest(
        compliance_targets=["NIST_AI_RMF", "FIXTURE"], framework_inputs=FIXTURE_INPUTS
    )
    code, _, stderr = cli("check", "--with-gaps")
    assert code == 1, stderr
    artifact = json.loads(Path("compliance-artifact.json").read_text())
    # Targets only, in target order; the EU AI Act report stays gap_report.
    assert list(artifact["framework_reports"]) == ["NIST_AI_RMF", "FIXTURE"]
    assert artifact["gap_report"]["articles"][0]["article"] == "Art. 4"
    fixture = artifact["framework_reports"]["FIXTURE"]
    assert fixture["gated"] is False
    assert fixture["excluded"] == {"FIXTURE:REQ-3": "No deployers: internal tool only."}
    rows = {row["article"]: row for row in fixture["report"]["articles"]}
    assert rows["FIXTURE:REQ-2"]["confidence_label"] == "attested"

    # `report` reads them from the artifact without a --gap-report file.
    code, _, stderr = cli("report", "-o", "report.html")
    assert code == 0, stderr
    page = Path("report.html").read_text(encoding="utf-8")
    assert "<h2>Fixture framework</h2>" in page
    assert "<li>FIXTURE:REQ-3: No deployers: internal tool only.</li>" in page


def test_check_unknown_target_exits_2_before_writing(cli):
    code, _, stderr = cli("check", "--with-gaps", "--target", "ISO_42001")
    assert code == 2
    assert "ISO_42001" in stderr
    assert not Path("compliance-artifact.json").exists()


def test_check_bad_framework_inputs_exit_2_without_artifact(cli, fixture_pack):
    _set_manifest(
        compliance_targets=["EU_AI_ACT", "FIXTURE"],
        framework_inputs={"FIXTURE": {"excluded": {"FIXTURE:NOPE": "n/a"}}},
    )
    code, _, stderr = cli("check", "--with-gaps")
    assert code == 2
    assert "FIXTURE:NOPE" in stderr
    assert not Path("compliance-artifact.json").exists()


def _fix_names(cli, *args: str, output_dir: str = "fixes") -> set[str]:
    code, _, stderr = cli("recommend", *args, "--output", output_dir)
    assert code == 0, stderr
    return {path.name for path in Path(output_dir).iterdir()}


def _write_gaps_json(cli, path: str = "gaps.json") -> str:
    code, stdout, stderr = cli("gaps", "--output", "json")
    assert code == 0, stderr
    Path(path).write_text(stdout, encoding="utf-8")
    return path


def test_recommend_adds_generic_fixes_for_native_framework_rows(cli, fixture_pack):
    eu_names = _fix_names(cli, output_dir="fixes-eu")
    _set_manifest(
        compliance_targets=["EU_AI_ACT", "FIXTURE"], framework_inputs=FIXTURE_INPUTS
    )

    # REQ-1 is Partial; REQ-2 is attested (Met) and REQ-3 excluded.
    assert _fix_names(cli) == eu_names | {"fixture--req-1-generic_requirement.md"}
    content = Path("fixes", "fixture--req-1-generic_requirement.md").read_text(
        encoding="utf-8"
    )
    assert "**Requirement:** Risk register maintained" in content
    assert "`framework_inputs.FIXTURE.attested`" in content


def test_recommend_skips_derived_nist_rows(cli):
    eu_names = _fix_names(cli, output_dir="fixes-eu")
    _set_manifest(compliance_targets=["EU_AI_ACT", "NIST_AI_RMF"])
    assert _fix_names(cli) == eu_names


def test_recommend_from_gaps_json_adds_native_framework_fixes(cli, fixture_pack):
    _set_manifest(compliance_targets=["EU_AI_ACT", "FIXTURE"])
    gaps_file = _write_gaps_json(cli)

    names = _fix_names(cli, "--gap-report", gaps_file)
    assert {
        "art9-risk_register_entry.md",
        "fixture--req-1-generic_requirement.md",
        "fixture--req-3-generic_requirement.md",
    } <= names


def test_report_from_gaps_json_renders_one_section_per_other_framework(
    cli, fixture_pack
):
    _set_manifest(
        compliance_targets=["EU_AI_ACT", "NIST_AI_RMF", "FIXTURE"],
        framework_inputs=FIXTURE_INPUTS,
    )
    gaps_file = _write_gaps_json(cli)

    code, _, stderr = cli("report", "--gap-report", gaps_file, "-o", "report.html")
    assert code == 0, stderr
    page = Path("report.html").read_text(encoding="utf-8")

    headings = re.findall(r"<h2>([^<]*)</h2>", page)
    gap_at = headings.index("Gap report")
    assert headings[gap_at + 1 : gap_at + 4] == [
        "NIST AI RMF 1.0 (derived from EU AI Act evidence)",
        "Fixture framework",
        "Eval summary",
    ]
    assert "derived from EU_AI_ACT" in page
    assert "<li>FIXTURE:REQ-3: No deployers: internal tool only.</li>" in page
    # The attestation statement is the provider's own words: escaped.
    assert html.escape(STATEMENT) in page

    envelope = json.loads(
        html.unescape(
            re.search(r'<script id="oc-envelope"[^>]*>(.*?)</script>', page)[1]
        )
    )
    assert envelope["disclaimer"] == DISCLAIMER_V2
    assert list(envelope["payload"]["framework_reports"]) == [
        "EU_AI_ACT",
        "NIST_AI_RMF",
        "FIXTURE",
    ]
